"""
GeoIP Client for IP Geolocation.

Features:
- MaxMind GeoIP2 database lookups
- IP to location mapping
- LRU caching
- Fallback for missing database
"""

import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)

# Try to import geoip2
try:
    import geoip2.database
    import geoip2.errors
    GEOIP2_AVAILABLE = True
except ImportError:
    GEOIP2_AVAILABLE = False
    logger.warning("geoip2 not available, using mock geolocation")


@dataclass
class GeoLocation:
    """Geolocation result for an IP address."""
    ip_address: str
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    is_anonymous_proxy: bool = False
    is_satellite_provider: bool = False
    accuracy_radius_km: Optional[int] = None
    
    @property
    def coordinates(self) -> Optional[tuple]:
        """Get (latitude, longitude) tuple."""
        if self.latitude is not None and self.longitude is not None:
            return (self.latitude, self.longitude)
        return None
    
    @property
    def display_location(self) -> str:
        """Get human-readable location string."""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.region:
            parts.append(self.region)
        if self.country_name:
            parts.append(self.country_name)
        return ', '.join(parts) if parts else 'Unknown'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'ip_address': self.ip_address,
            'country_code': self.country_code,
            'country_name': self.country_name,
            'city': self.city,
            'region': self.region,
            'postal_code': self.postal_code,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'timezone': self.timezone,
            'is_anonymous_proxy': self.is_anonymous_proxy,
            'display_location': self.display_location
        }


# Mock data for testing
MOCK_LOCATIONS = {
    '8.8.8.8': GeoLocation(
        ip_address='8.8.8.8',
        country_code='US',
        country_name='United States',
        city='Mountain View',
        region='California',
        latitude=37.386,
        longitude=-122.0838,
        timezone='America/Los_Angeles'
    ),
    '1.1.1.1': GeoLocation(
        ip_address='1.1.1.1',
        country_code='AU',
        country_name='Australia',
        city='Sydney',
        region='New South Wales',
        latitude=-33.8678,
        longitude=151.2073,
        timezone='Australia/Sydney'
    ),
    '185.220.101.1': GeoLocation(
        ip_address='185.220.101.1',
        country_code='DE',
        country_name='Germany',
        city='Frankfurt',
        region='Hesse',
        latitude=50.1109,
        longitude=8.6821,
        timezone='Europe/Berlin',
        is_anonymous_proxy=True
    ),
    '91.234.56.78': GeoLocation(
        ip_address='91.234.56.78',
        country_code='RU',
        country_name='Russia',
        city='Moscow',
        region='Moscow',
        latitude=55.7558,
        longitude=37.6173,
        timezone='Europe/Moscow'
    ),
    '202.14.88.99': GeoLocation(
        ip_address='202.14.88.99',
        country_code='CN',
        country_name='China',
        city='Beijing',
        region='Beijing',
        latitude=39.9042,
        longitude=116.4074,
        timezone='Asia/Shanghai'
    )
}


class GeoIPClient:
    """GeoIP lookup client using MaxMind database."""
    
    def __init__(self, geoip_config, use_mock: bool = False):
        """Initialize GeoIP client."""
        self.config = geoip_config
        self.use_mock = use_mock or not GEOIP2_AVAILABLE
        self._reader = None
        
        # Metrics
        self.total_lookups = 0
        self.cache_hits = 0
        self.lookup_errors = 0
        
        # LRU cache
        self._cache: Dict[str, GeoLocation] = {}
        self._cache_max_size = geoip_config.cache_size
        
        if not self.use_mock:
            self._init_reader()
    
    def _init_reader(self):
        """Initialize GeoIP2 database reader."""
        try:
            if self.config.is_configured():
                self._reader = geoip2.database.Reader(self.config.database_path)
                logger.info(f"GeoIP database loaded: {self.config.database_path}")
            else:
                logger.warning("GeoIP database not found, using mock data")
                self.use_mock = True
        except Exception as e:
            logger.error(f"Failed to load GeoIP database: {e}")
            self.use_mock = True
    
    def lookup(self, ip_address: str) -> GeoLocation:
        """Look up geolocation for IP address."""
        self.total_lookups += 1
        
        # Check cache
        if ip_address in self._cache:
            self.cache_hits += 1
            return self._cache[ip_address]
        
        # Perform lookup
        if self.use_mock:
            result = self._mock_lookup(ip_address)
        else:
            result = self._real_lookup(ip_address)
        
        # Cache result
        self._add_to_cache(ip_address, result)
        
        return result
    
    def _real_lookup(self, ip_address: str) -> GeoLocation:
        """Perform real GeoIP lookup."""
        try:
            response = self._reader.city(ip_address)
            
            return GeoLocation(
                ip_address=ip_address,
                country_code=response.country.iso_code,
                country_name=response.country.name,
                city=response.city.name,
                region=response.subdivisions.most_specific.name if response.subdivisions else None,
                postal_code=response.postal.code,
                latitude=response.location.latitude,
                longitude=response.location.longitude,
                timezone=response.location.time_zone,
                is_anonymous_proxy=response.traits.is_anonymous_proxy,
                is_satellite_provider=response.traits.is_satellite_provider,
                accuracy_radius_km=response.location.accuracy_radius
            )
            
        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"IP not found in database: {ip_address}")
            return GeoLocation(ip_address=ip_address)
            
        except Exception as e:
            self.lookup_errors += 1
            logger.error(f"GeoIP lookup error for {ip_address}: {e}")
            return GeoLocation(ip_address=ip_address)
    
    def _mock_lookup(self, ip_address: str) -> GeoLocation:
        """Return mock geolocation data."""
        if ip_address in MOCK_LOCATIONS:
            return MOCK_LOCATIONS[ip_address]
        
        # Generate consistent mock data based on IP
        octets = ip_address.split('.')
        if len(octets) == 4:
            first_octet = int(octets[0])
            
            # Rough geographic distribution by first octet
            if first_octet < 50:
                return GeoLocation(
                    ip_address=ip_address,
                    country_code='US',
                    country_name='United States',
                    city='New York',
                    region='New York',
                    latitude=40.7128,
                    longitude=-74.0060,
                    timezone='America/New_York'
                )
            elif first_octet < 100:
                return GeoLocation(
                    ip_address=ip_address,
                    country_code='EU',
                    country_name='European Union',
                    city='London',
                    region='England',
                    latitude=51.5074,
                    longitude=-0.1278,
                    timezone='Europe/London'
                )
            elif first_octet < 150:
                return GeoLocation(
                    ip_address=ip_address,
                    country_code='JP',
                    country_name='Japan',
                    city='Tokyo',
                    region='Tokyo',
                    latitude=35.6762,
                    longitude=139.6503,
                    timezone='Asia/Tokyo'
                )
            else:
                return GeoLocation(
                    ip_address=ip_address,
                    country_code='BR',
                    country_name='Brazil',
                    city='São Paulo',
                    region='São Paulo',
                    latitude=-23.5505,
                    longitude=-46.6333,
                    timezone='America/Sao_Paulo'
                )
        
        return GeoLocation(ip_address=ip_address)
    
    def _add_to_cache(self, ip_address: str, location: GeoLocation):
        """Add location to cache with LRU eviction."""
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[ip_address] = location
    
    def batch_lookup(self, ip_addresses: list) -> Dict[str, GeoLocation]:
        """Look up multiple IP addresses."""
        return {ip: self.lookup(ip) for ip in ip_addresses}
    
    def is_high_risk_location(self, ip_address: str) -> bool:
        """Check if IP is from high-risk location."""
        location = self.lookup(ip_address)
        
        # Check anonymous proxy
        if location.is_anonymous_proxy:
            return True
        
        # Add custom high-risk country logic
        high_risk_countries = {'KP', 'IR', 'SY'}  # Example
        if location.country_code in high_risk_countries:
            return True
        
        return False
    
    def get_threat_context(self, ip_address: str) -> Dict[str, Any]:
        """Get threat context for IP address."""
        location = self.lookup(ip_address)
        
        return {
            'ip_address': ip_address,
            'location': location.display_location,
            'country_code': location.country_code,
            'is_anonymous_proxy': location.is_anonymous_proxy,
            'is_satellite_provider': location.is_satellite_provider,
            'is_high_risk': self.is_high_risk_location(ip_address),
            'coordinates': location.coordinates,
            'timezone': location.timezone
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get GeoIP client metrics."""
        hit_rate = (self.cache_hits / max(1, self.total_lookups)) * 100
        
        return {
            'total_lookups': self.total_lookups,
            'cache_hits': self.cache_hits,
            'cache_hit_rate': round(hit_rate, 1),
            'lookup_errors': self.lookup_errors,
            'cache_size': len(self._cache),
            'using_mock': self.use_mock,
            'database_configured': self.config.is_configured()
        }
    
    def close(self):
        """Close database reader."""
        if self._reader:
            self._reader.close()
            logger.info("GeoIP database reader closed")


__all__ = ['GeoIPClient', 'GeoLocation', 'GEOIP2_AVAILABLE', 'MOCK_LOCATIONS']
