from owlready2 import *
from pathlib import Path

# Make sure data folder exists
Path("data").mkdir(exist_ok=True)

# Create ontology
onto = get_ontology("http://example.org/cybersecurity_ontology.owl")

with onto:
    # Main ontology classes
    class CybersecurityDomain(Thing):
        pass

    class Keyword(Thing):
        pass

    # Object properties
    class hasKeyword(ObjectProperty):
        domain = [CybersecurityDomain]
        range = [Keyword]

    class relatedTo(ObjectProperty):
        domain = [CybersecurityDomain]
        range = [CybersecurityDomain]

    # Cybersecurity domain classes
    class Governance(CybersecurityDomain):
        pass

    class RiskManagement(CybersecurityDomain):
        pass

    class AccessControl(CybersecurityDomain):
        pass

    class Cryptography(CybersecurityDomain):
        pass

    class NetworkSecurity(CybersecurityDomain):
        pass

    class OperationalSecurity(CybersecurityDomain):
        pass

    class PhysicalSecurity(CybersecurityDomain):
        pass

    class ApplicationSecurity(CybersecurityDomain):
        pass

    class DataSecurity(CybersecurityDomain):
        pass


# Helper function to safely create keyword individuals
def create_keyword(name):
    clean_name = name.replace(" ", "_").replace("-", "_").replace("/", "_")
    return Keyword(clean_name)


# Create domain individuals
governance = Governance("GOVERNANCE")
risk_mgmt = RiskManagement("RISK_MGMT")
access_control = AccessControl("ACCESS_CONTROL")
cryptography = Cryptography("CRYPTOGRAPHY")
network_sec = NetworkSecurity("NETWORK_SEC")
ops_sec = OperationalSecurity("OPS_SEC")
physical_sec = PhysicalSecurity("PHYSICAL_SEC")
app_sec = ApplicationSecurity("APP_SEC")
data_sec = DataSecurity("DATA_SEC")


# Define keywords for each domain
domain_keywords = {
    governance: [
        "strategy", "policy", "roles", "legal", "compliance",
        "audit", "governance", "leadership", "framework"
    ],
    risk_mgmt: [
        "risk", "assessment", "mitigation", "impact", "vulnerability",
        "threat", "treatment", "register"
    ],
    access_control: [
        "identity", "authentication", "iam", "privilege", "password",
        "mfa", "authorization", "access"
    ],
    cryptography: [
        "encryption", "key", "algorithm", "tls", "hash",
        "signature", "pki", "cipher", "cryptographic"
    ],
    network_sec: [
        "firewall", "ips", "ids", "vpn", "router",
        "segmentation", "dmz", "wifi", "port", "protocol"
    ],
    ops_sec: [
        "backup", "recovery", "redundancy", "patch", "malware",
        "antivirus", "logging", "monitoring", "incident"
    ],
    physical_sec: [
        "camera", "lock", "badge", "perimeter", "guard",
        "facility", "environmental", "biometric"
    ],
    app_sec: [
        "software", "devsecops", "coding", "api", "web",
        "injection", "testing", "lifecycle", "development"
    ],
    data_sec: [
        "classification", "labeling", "privacy", "dlp", "masking",
        "anonymization", "retention", "integrity"
    ]
}


# Attach keywords to domains using OWL property: hasKeyword
for domain, keywords in domain_keywords.items():
    for kw in keywords:
        keyword_individual = create_keyword(kw)
        domain.hasKeyword.append(keyword_individual)


# Define semantic relationships using OWL property: relatedTo
governance.relatedTo = [risk_mgmt, data_sec, ops_sec]
risk_mgmt.relatedTo = [governance, ops_sec, data_sec]
access_control.relatedTo = [network_sec, physical_sec, app_sec]


# Save ontology as OWL/RDF XML
onto.save(file="data/cybersecurity_ontology.owl", format="rdfxml")

print("OWL ontology created successfully at data/cybersecurity_ontology.owl")