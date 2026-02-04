"""
Test fixtures for Epic connector tests.

This module provides test RSA keys and sample data for Epic integration testing.
DO NOT use these keys in production - they are for testing only.
"""

# RSA 2048-bit Private Key for Testing
# Generated specifically for unit tests - DO NOT use in production
TEST_RSA_PRIVATE_KEY_PEM = """-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEA2Z3qX2BTLS4e0rylwQqURFtXCnpVDcB3Ge5HaD9B4j4EHxkY
kQjQJqJmCCnM/SB0TU0MbBHNmGNqRhsZL8bF9rTbbqV7MTgQ8cR9nGvkZmFOGYtD
FvLqMkz6l9FGwwgg77C0G6/k8hM7A3DqWg6xyGfWGSkD0DIHQ6kPHxJFMdHD9MHf
F7gO3+jD0qLpJ0dVPt8DNUJzhw0g2cKQPT0p3aOTZLfC+NYrPbJCNTLSP3Q3r6eD
gI+h4DKqg3Qthj/HfVh4DhuX/nSMYQPHJ3eXJy/pKqfzHhLdF7wwvGg7BqVL0w4J
mOJrE3rnDPHN9kHMKspJHgJ7aUwzPbJTf/HgewIDAQABAoIBAA7SGHV6GKPbJDnf
dHRf4hPmhENhv5ClNAdB3Y4lQVhJpQh3uWBDPMAH7HM8YFSn0U6p8ZkpR2gLQz4h
E5+xyFLPFn1REdETm8rOMMnmMhKDrHbX3LJQFHI1FJPJaTGDPjLZl5JXw5KRDzXS
GGDY8P9z9F/8G2QSPDsL9Lf8D5yKoD8DZuA3ylP5FfRAqJIF5xPtnJKqlhF5R/xX
q5Q3Gd4YBj5K+U3bgPruhIm+VbX4PEmRJyQw0/qgL3rOVj18QJUQ9LRrPR6mRPrn
qj5FTKi2BqBLPF5XoPJCqF7jqLtVh8FqH+x1trDP/VEQX3JBT0QXFJf/cOO3IqpV
3sSvPQECgYEA8qTBqZPvC5HGhh6F8RLiOP0/BqS7qbT7M6MByF5FvPwJZCnKPZ4z
cOSuPcTn8V1EiNro5c8WvFKJNfJg5wLnVySsCN+IsYPlwBJKS8ySH5Qw0Pow/0rF
F7QQVF0Cqk6yJkglPVl1E7pIoiLl5FjKk0cNmNnVPRi/mmqM/R0FswsCgYEA5RB0
Fckq8dfTiOvSdqVH3nOLMQ8QsVDBIwi05T7ykx8Fvp2HHNjB/rnfp4Bxwey6oB0G
Mn4xAJmVfHU9p0Voef9FlfPTVkqLIEjUvBpJbMgJp2udqWQaYwBJ/S8jJCCnM/SB
0TU0MbBHNmGNqRhsZL8bF9rTbbqV7MTgQ8cR9nECgYEA2cBADq27bVBHf4S3JdhE
4xfUTxPLjH4tDn8cCR1HJqQM6B7WNJ5nWRqKJnT0j5J6AEdJPNYqLHprQ9VYcF5K
c5f2FGhKDdhNfPS0AuuF7RBY0gT0tVAPd8kPF6wM/IwMN0T+PVmqVfP5D+G5hVqj
AxNH1T3M/wIYcjeDS5z6OtsCgYEAqvz0+F5S3hMu/nP3u6XHf5S3JiKCTl2RFABN
I0qEpmnZljPFdxqzFmLnKKPLZJC6bP0tXf8QJOQK9F8GCHfSJF5SHjPNey1KhpRF
zLyYq8z3r5Q4GfvVd5BGMv8mKJjD+HJxSLnN6f5I0FZhPJ2FTHR0n6p7JyEJNsm0
I3nvpIECgYBpVDbN/ICVPrZHjQVVCN7q7OyJBtT3NL0M9pPf9VfQBvXL1Pf9cRug
VtqV9FXd7KJwPQHfwqF2THPI1F2FJzFJf2Dn2IXb1qLb6h9SFFF6xapY8Pd+C6hC
DSJAHT1qt6E9P1dBz6ZOqC6G/bj8FGWAPFQEK1sW1z6LNq8y5E7Xvw==
-----END RSA PRIVATE KEY-----"""

# Corresponding Public Key (for verification in tests)
TEST_RSA_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2Z3qX2BTLS4e0rylwQqU
RFtXCnpVDcB3Ge5HaD9B4j4EHxkYkQjQJqJmCCnM/SB0TU0MbBHNmGNqRhsZL8bF
9rTbbqV7MTgQ8cR9nGvkZmFOGYtDFvLqMkz6l9FGwwgg77C0G6/k8hM7A3DqWg6x
yGfWGSkD0DIHQ6kPHxJFMdHD9MHfF7gO3+jD0qLpJ0dVPt8DNUJzhw0g2cKQPT0p
3aOTZLfC+NYrPbJCNTLSP3Q3r6eDgI+h4DKqg3Qthj/HfVh4DhuX/nSMYQPHJ3eX
Jy/pKqfzHhLdF7wwvGg7BqVL0w4JmOJrE3rnDPHN9kHMKspJHgJ7aUwzPbJTf/Hg
ewIDAQAB
-----END PUBLIC KEY-----"""

# Sample Epic sandbox patient data
SAMPLE_EPIC_PATIENTS = {
    "derrick_lin": {
        "resourceType": "Patient",
        "id": "Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB",
        "name": [{"use": "official", "family": "Lin", "given": ["Derrick"]}],
        "gender": "male",
        "birthDate": "1973-06-03"
    },
    "mychart_amy": {
        "resourceType": "Patient",
        "id": "erXuFYUfucBZaryVksYEcMg3",
        "name": [{"use": "official", "family": "Smith", "given": ["Amy"]}],
        "gender": "female",
        "birthDate": "1985-08-15"
    },
    "mychart_billy": {
        "resourceType": "Patient",
        "id": "eq081-VQEgP8drUUqCWzHfw3",
        "name": [{"use": "official", "family": "Jones", "given": ["Billy"]}],
        "gender": "male",
        "birthDate": "1990-12-25"
    }
}

# Sample Epic observation data
SAMPLE_EPIC_OBSERVATIONS = {
    "vital_signs": {
        "resourceType": "Observation",
        "id": "vs-123",
        "status": "final",
        "category": [{"coding": [{"code": "vital-signs"}]}],
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]
        },
        "valueQuantity": {"value": 72, "unit": "/min"}
    },
    "lab_result": {
        "resourceType": "Observation",
        "id": "lab-456",
        "status": "final",
        "category": [{"coding": [{"code": "laboratory"}]}],
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c"}]
        },
        "valueQuantity": {"value": 6.5, "unit": "%"}
    }
}

# Sample Epic capability statement
SAMPLE_EPIC_CAPABILITY_STATEMENT = {
    "resourceType": "CapabilityStatement",
    "status": "active",
    "date": "2024-01-01",
    "publisher": "Epic",
    "kind": "instance",
    "software": {
        "name": "Epic",
        "version": "2024"
    },
    "fhirVersion": "4.0.1",
    "format": ["json", "xml"],
    "rest": [
        {
            "mode": "server",
            "resource": [
                {"type": "Patient"},
                {"type": "Observation"},
                {"type": "Condition"},
                {"type": "MedicationRequest"},
                {"type": "DocumentReference"},
                {"type": "DiagnosticReport"},
                {"type": "Encounter"},
                {"type": "Practitioner"}
            ]
        }
    ]
}

# Sample Epic token response
SAMPLE_EPIC_TOKEN_RESPONSE = {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.example-token",
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": "system/Patient.read system/Observation.read system/Condition.read"
}
