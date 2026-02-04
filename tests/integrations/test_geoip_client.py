"""
Tests for GeoIP Client.
"""

import pytest
from unittest.mock import patch, MagicMock

from phoenix_guardian.config.production_config import GeoIPConfig
from phoenix_guardian.integrations.geoip_client import (
    GeoIPClient,
    GeoLocation,
    GEOIP2_AVAILABLE,
    MOCK_LOCATIONS
)


class TestGeoLocation:
    """Tests for GeoLocation dataclass."""
    
    def test_basic_location(self):
        """Test basic location creation."""
        loc = GeoLocation(
            ip_address='8.8.8.8',
            country_code='US',
            country_name='United States',
            city='Mountain View'
        )
        
        assert loc.ip_address == '8.8.8.8'
        assert loc.country_code == 'US'
    
    def test_coordinates_property(self):
        """Test coordinates tuple property."""
        loc = GeoLocation(
            ip_address='1.1.1.1',
            latitude=37.386,
            longitude=-122.084
        )
        
        coords = loc.coordinates
        assert coords == (37.386, -122.084)
    
    def test_coordinates_none_when_missing(self):
        """Test coordinates is None when lat/lon missing."""
        loc = GeoLocation(ip_address='1.1.1.1')
        assert loc.coordinates is None
    
    def test_display_location(self):
        """Test human-readable location string."""
        loc = GeoLocation(
            ip_address='1.1.1.1',
            city='San Francisco',
            region='California',
            country_name='United States'
        )
        
        assert loc.display_location == 'San Francisco, California, United States'
    
    def test_display_location_partial(self):
        """Test display with partial data."""
        loc = GeoLocation(
            ip_address='1.1.1.1',
            country_name='Germany'
        )
        
        assert loc.display_location == 'Germany'
    
    def test_display_location_unknown(self):
        """Test display when no location data."""
        loc = GeoLocation(ip_address='1.1.1.1')
        assert loc.display_location == 'Unknown'
    
    def test_to_dict(self):
        """Test dictionary conversion."""
        loc = GeoLocation(
            ip_address='8.8.8.8',
            country_code='US',
            city='Test City',
            is_anonymous_proxy=True
        )
        
        data = loc.to_dict()
        
        assert data['ip_address'] == '8.8.8.8'
        assert data['country_code'] == 'US'
        assert data['is_anonymous_proxy'] is True
        assert 'display_location' in data


class TestMockLocations:
    """Tests for mock location data."""
    
    def test_known_ips_available(self):
        """Test mock data includes known IPs."""
        assert '8.8.8.8' in MOCK_LOCATIONS
        assert '1.1.1.1' in MOCK_LOCATIONS
    
    def test_mock_data_structure(self):
        """Test mock data has correct structure."""
        google_dns = MOCK_LOCATIONS['8.8.8.8']
        
        assert google_dns.country_code == 'US'
        assert google_dns.city == 'Mountain View'
        assert google_dns.latitude is not None


class TestGeoIPClient:
    """Tests for GeoIP client."""
    
    @pytest.fixture
    def geoip_config(self):
        """Create test GeoIP config."""
        return GeoIPConfig(
            database_path='/fake/path/GeoLite2.mmdb',
            cache_size=100
        )
    
    @pytest.fixture
    def mock_client(self, geoip_config):
        """Create mock GeoIP client."""
        return GeoIPClient(geoip_config, use_mock=True)
    
    def test_init(self, geoip_config):
        """Test client initialization."""
        client = GeoIPClient(geoip_config, use_mock=True)
        
        assert client.use_mock is True
        assert client.total_lookups == 0
    
    def test_lookup_known_ip(self, mock_client):
        """Test lookup for known IP."""
        result = mock_client.lookup('8.8.8.8')
        
        assert result.ip_address == '8.8.8.8'
        assert result.country_code == 'US'
        assert result.city == 'Mountain View'
        assert mock_client.total_lookups == 1
    
    def test_lookup_unknown_ip(self, mock_client):
        """Test lookup for unknown IP gets generated data."""
        result = mock_client.lookup('99.99.99.99')
        
        assert result.ip_address == '99.99.99.99'
        assert result.country_code is not None
    
    def test_cache_hit(self, mock_client):
        """Test cache hit on second lookup."""
        mock_client.lookup('8.8.8.8')
        mock_client.lookup('8.8.8.8')
        
        assert mock_client.cache_hits == 1
        assert mock_client.total_lookups == 2
    
    def test_batch_lookup(self, mock_client):
        """Test batch IP lookup."""
        ips = ['8.8.8.8', '1.1.1.1', '10.0.0.1']
        results = mock_client.batch_lookup(ips)
        
        assert len(results) == 3
        assert all(ip in results for ip in ips)
    
    def test_is_high_risk_proxy(self, mock_client):
        """Test anonymous proxy detection."""
        # 185.220.101.1 is marked as anonymous proxy in mock data
        is_risky = mock_client.is_high_risk_location('185.220.101.1')
        assert is_risky is True
    
    def test_is_high_risk_normal(self, mock_client):
        """Test normal IP is not high risk."""
        is_risky = mock_client.is_high_risk_location('8.8.8.8')
        assert is_risky is False
    
    def test_get_threat_context(self, mock_client):
        """Test threat context generation."""
        context = mock_client.get_threat_context('8.8.8.8')
        
        assert context['ip_address'] == '8.8.8.8'
        assert context['country_code'] == 'US'
        assert 'is_anonymous_proxy' in context
        assert 'is_high_risk' in context
    
    def test_get_metrics(self, mock_client):
        """Test metrics collection."""
        mock_client.lookup('8.8.8.8')
        mock_client.lookup('1.1.1.1')
        mock_client.lookup('8.8.8.8')  # Cache hit
        
        metrics = mock_client.get_metrics()
        
        assert metrics['total_lookups'] == 3
        assert metrics['cache_hits'] == 1
        assert metrics['cache_hit_rate'] > 30
        assert metrics['cache_size'] == 2


class TestGeoIPCaching:
    """Tests for LRU caching behavior."""
    
    def test_cache_eviction(self):
        """Test cache evicts oldest entries."""
        config = GeoIPConfig(cache_size=2)
        client = GeoIPClient(config, use_mock=True)
        
        # Fill cache
        client.lookup('8.8.8.8')
        client.lookup('1.1.1.1')
        
        # This should evict first entry
        client.lookup('10.0.0.1')
        
        assert len(client._cache) == 2
        assert '8.8.8.8' not in client._cache
        assert '1.1.1.1' in client._cache
        assert '10.0.0.1' in client._cache


class TestGeoIPMockDataGeneration:
    """Tests for mock data generation."""
    
    @pytest.fixture
    def mock_client(self):
        """Create mock client."""
        config = GeoIPConfig()
        return GeoIPClient(config, use_mock=True)
    
    def test_low_octet_returns_us(self, mock_client):
        """Test low first octet returns US location."""
        result = mock_client._mock_lookup('10.0.0.1')
        assert result.country_code == 'US'
    
    def test_mid_octet_returns_eu(self, mock_client):
        """Test mid first octet returns EU location."""
        result = mock_client._mock_lookup('60.0.0.1')
        assert result.country_code == 'EU'
    
    def test_high_octet_returns_japan(self, mock_client):
        """Test higher octet returns Japan."""
        result = mock_client._mock_lookup('120.0.0.1')
        assert result.country_code == 'JP'


class TestGeoIPClose:
    """Tests for resource cleanup."""
    
    def test_close_mock(self):
        """Test closing mock client."""
        config = GeoIPConfig()
        client = GeoIPClient(config, use_mock=True)
        
        client.close()
        # Should not raise
    
    @pytest.mark.skipif(not GEOIP2_AVAILABLE, reason="geoip2 not installed")
    def test_close_real_reader(self):
        """Test closing real reader."""
        # Would need actual database file
        pass
