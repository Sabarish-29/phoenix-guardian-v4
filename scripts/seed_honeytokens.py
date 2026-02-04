"""
Seed honeytoken records into database.

Honeytokens are fake patient records designed to detect unauthorized access.
When someone accesses a honeytoken, it triggers a security alert because
legitimate users would never access these fake records.

Usage:
    python scripts/seed_honeytokens.py           # Seed 50 honeytokens
    python scripts/seed_honeytokens.py --count 100  # Seed 100 honeytokens
    python scripts/seed_honeytokens.py --verify  # Verify existing honeytokens
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from phoenix_guardian.security import (
    HoneytokenGenerator,
    MRN_RANGE_MIN,
    MRN_RANGE_MAX,
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def generate_honeytokens(count: int = 50) -> list:
    """
    Generate honeytoken patient records.
    
    Args:
        count: Number of honeytokens to generate
        
    Returns:
        List of generated honeytoken records
    """
    generator = HoneytokenGenerator()
    honeytokens = []
    
    logger.info(f"Generating {count} honeytoken patient records...")
    
    for i in range(count):
        try:
            # Generate honeytoken using the existing generator
            honeytoken = generator.generate(attack_type="seeding")
            
            # Create simplified record for storage/export
            record = {
                "mrn": honeytoken.mrn,
                "patient_name": honeytoken.patient_name,
                "phone": honeytoken.phone,
                "email": honeytoken.email,
                "address": honeytoken.address,
                "token_id": honeytoken.id,
                "created_at": datetime.utcnow().isoformat(),
                "is_honeytoken": True,
                "status": "active"
            }
            
            honeytokens.append(record)
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Generated {i + 1}/{count} honeytokens...")
                
        except Exception as e:
            logger.error(f"Error generating honeytoken {i + 1}: {e}")
            continue
    
    return honeytokens


def save_honeytokens_to_file(honeytokens: list, output_file: str = None) -> str:
    """
    Save honeytokens to a JSON file for reference.
    
    Args:
        honeytokens: List of honeytoken records
        output_file: Optional output file path
        
    Returns:
        Path to saved file
    """
    if output_file is None:
        output_file = project_root / "data" / "honeytokens_seeded.json"
    else:
        output_file = Path(output_file)
    
    # Ensure directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Save with metadata
    data = {
        "generated_at": datetime.utcnow().isoformat(),
        "count": len(honeytokens),
        "mrn_range": {
            "min": MRN_RANGE_MIN,
            "max": MRN_RANGE_MAX
        },
        "honeytokens": honeytokens
    }
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    return str(output_file)


def verify_honeytokens() -> dict:
    """
    Verify existing honeytokens.
    
    Returns:
        Verification results
    """
    honeytoken_file = project_root / "data" / "honeytokens_seeded.json"
    
    if not honeytoken_file.exists():
        return {
            "status": "not_found",
            "message": "No honeytokens file found. Run seed_honeytokens.py first.",
            "count": 0
        }
    
    with open(honeytoken_file, 'r') as f:
        data = json.load(f)
    
    honeytokens = data.get("honeytokens", [])
    
    # Verify each honeytoken
    generator = HoneytokenGenerator()
    valid_count = 0
    invalid = []
    
    for ht in honeytokens:
        mrn = ht.get("mrn", "")
        # Check if MRN is in valid honeytoken range
        try:
            mrn_number = int(mrn.replace("MRN-", "").replace("HT-", ""))
            if MRN_RANGE_MIN <= mrn_number <= MRN_RANGE_MAX:
                valid_count += 1
            else:
                invalid.append(mrn)
        except ValueError:
            invalid.append(mrn)
    
    return {
        "status": "verified",
        "total_count": len(honeytokens),
        "valid_count": valid_count,
        "invalid_count": len(invalid),
        "invalid_mrns": invalid[:10],  # First 10 only
        "generated_at": data.get("generated_at"),
        "file_path": str(honeytoken_file)
    }


def main():
    """Main entry point for seeding honeytokens."""
    parser = argparse.ArgumentParser(
        description="Seed honeytoken records for security monitoring"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of honeytokens to generate (default: 50)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing honeytokens instead of generating new ones"
    )
    
    args = parser.parse_args()
    
    if args.verify:
        logger.info("Verifying existing honeytokens...")
        result = verify_honeytokens()
        
        if result["status"] == "not_found":
            logger.warning(f"⚠️  {result['message']}")
            sys.exit(1)
        
        logger.info(f"\n{'='*60}")
        logger.info("HONEYTOKEN VERIFICATION RESULTS")
        logger.info(f"{'='*60}")
        logger.info(f"Total honeytokens: {result['total_count']}")
        logger.info(f"Valid: {result['valid_count']}")
        logger.info(f"Invalid: {result['invalid_count']}")
        logger.info(f"Generated at: {result['generated_at']}")
        logger.info(f"File: {result['file_path']}")
        
        if result['invalid_count'] > 0:
            logger.warning(f"\n⚠️  Invalid MRNs (first 10): {result['invalid_mrns']}")
        else:
            logger.info("\n✅ All honeytokens are valid!")
        
        sys.exit(0)
    
    # Generate honeytokens
    logger.info(f"\n{'='*60}")
    logger.info("HONEYTOKEN SEEDING")
    logger.info(f"{'='*60}")
    
    honeytokens = generate_honeytokens(count=args.count)
    
    if not honeytokens:
        logger.error("❌ Failed to generate any honeytokens")
        sys.exit(1)
    
    # Save to file
    output_path = save_honeytokens_to_file(honeytokens, args.output)
    
    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("SEEDING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Generated {len(honeytokens)} honeytokens")
    logger.info(f"📁 Saved to: {output_path}")
    logger.info(f"\nMRN Range: {MRN_RANGE_MIN} - {MRN_RANGE_MAX}")
    logger.info(f"Prefix: MRN-9XXXXX (honeytokens)")
    
    # Show sample
    if honeytokens:
        logger.info(f"\n📋 Sample honeytoken:")
        sample = honeytokens[0]
        for key, value in sample.items():
            if key != "is_honeytoken":
                logger.info(f"   {key}: {value}")
    
    logger.info(f"\n⚠️  These records will trigger security alerts when accessed!")
    logger.info("   Monitor the security_incidents table for honeytoken triggers.")
    

if __name__ == "__main__":
    main()
