"""
Configuration for the Synthetic Criminal Network Investigation Dataset Generator.
All numbers here are deliberately small for a fast DEMO run. The architecture
does not change if you raise these to the full spec (100 cases / 1000 persons /
10,000 CDRs / etc.) — only runtime does. Bump DEMO_SCALE=False and raise the
numbers below to produce the full-scale dataset described in the brief.
"""

SEED = 2026

DEMO_SCALE = False

if DEMO_SCALE:
    N_CASES = 12                 # spec: 100+
    N_PERSONS = 140              # spec: 1000+
    N_ORGS = 25                  # spec: 150+
    N_VEHICLES = 45              # spec: 300+
    N_PHONES = 170               # spec: 1200+
    N_ACCOUNTS = 110              # spec: 800+
    N_LOCATIONS = 60             # spec: 300+
    CDR_PER_CASE_BG = 40         # background/noise calls per case (on top of network calls)
    TX_PER_CASE_BG = 6
else:
    N_CASES = 100
    N_PERSONS = 1000
    N_ORGS = 150
    N_VEHICLES = 300
    N_PHONES = 1200
    N_ACCOUNTS = 800
    N_LOCATIONS = 300
    CDR_PER_CASE_BG = 90
    TX_PER_CASE_BG = 45

# Difficulty distribution (must sum to N_CASES when scaled proportionally)
DIFFICULTY_RATIO = {
    "Basic": 0.20,
    "Intermediate": 0.30,
    "Advanced": 0.30,
    "Expert": 0.20,
}

DIFFICULTY_ENTITY_RANGE = {
    "Basic": (3, 8),
    "Intermediate": (8, 20),
    "Advanced": (20, 50),
    "Expert": (50, 80),   # capped for demo readability; spec says 50+
}

NOISE = {
    "missing_data": 0.07,
    "duplicates": 0.04,
    "aliases": 0.08,
    "spelling_variations": 0.05,
    "contradictions": 0.03,
    "false_leads": 0.10,
}

TOPOLOGIES = ["A_hierarchical", "B_chain", "C_dense_cluster", "D_two_communities_broker",
              "E_hub_spoke", "F_multi_hub", "G_hidden_bridge", "H_layered",
              "I_cross_case", "J_decoy_heavy"]

CRIME_TYPES = [
    "Financial Fraud", "Organized Theft", "Vehicle Theft Network", "Cyber-enabled Fraud",
    "Extortion", "Identity Fraud", "Corporate Fraud", "Document Forgery",
    "Smuggling-style Network", "Illegal Goods Distribution", "Insurance Fraud",
    "Investment Fraud", "Procurement Fraud", "Money-laundering-style Financial Network",
    "Missing-person Investigation", "Robbery Network", "Warehouse Theft",
    "Courier-based Criminal Network", "Fake-company Network", "Multi-city Fraud Network",
]

CITIES = [
    "Delhi", "Gurugram", "Faridabad", "Noida", "Ghaziabad", "Jaipur", "Chandigarh",
    "Lucknow", "Kanpur", "Agra", "Dehradun", "Haridwar", "Amritsar", "Ludhiana",
    "Mumbai", "Pune", "Ahmedabad", "Surat", "Indore", "Bhopal", "Hyderabad",
    "Bengaluru", "Chennai", "Kolkata", "Patna", "Ranchi", "Bhubaneswar",
]

AREA_TEMPLATES = [
    "Sector {n}", "Phase {n} Industrial Estate", "Model Town Block {letter}",
    "Civil Lines", "Commercial Block {letter}", "Old City Market", "Railway Colony",
    "New Township Sector {n}", "Housing Board Colony", "Transport Nagar",
]

LOCATION_NAME_TEMPLATES = {
    "residential": ["{area} Residency", "{area} Apartments", "{area} Housing Complex"],
    "commercial": ["{area} Commercial Complex", "{area} Trade Centre", "{area} Market"],
    "industrial": ["{area} Industrial Estate", "{area} Warehouse Zone"],
    "office": ["{area} Business Tower", "{area} Corporate Plaza"],
    "warehouse": ["{area} Storage Yard", "{area} Logistics Warehouse"],
    "hotel": ["Hotel {area} Regency", "{area} Inn"],
    "restaurant": ["{area} Family Restaurant", "{area} Dhaba"],
    "transport": ["{area} Bus Terminal", "{area} Railway Station"],
    "parking": ["{area} Public Parking", "{area} Multi-level Parking"],
    "public": ["{area} Community Park", "{area} Public Ground"],
}

MALE_FIRST = ["Arjun","Rohan","Vikram","Aditya","Karan","Nikhil","Sameer","Rajat","Manish",
              "Rohit","Neeraj","Aakash","Deepak","Vivek","Suresh","Anil","Ramesh","Ashok",
              "Gaurav","Tarun","Harish","Mohit","Yash","Siddharth","Rajesh","Sanjay",
              "Ravi","Naveen","Pankaj","Amit"]
FEMALE_FIRST = ["Priya","Ananya","Kavya","Simran","Sneha","Pooja","Neha","Divya","Ritu",
                "Anjali","Shruti","Meera","Kirti","Swati","Isha","Nidhi","Rekha","Sunita",
                "Kajal","Payal","Aarti","Bhavna","Charu","Tanya","Vidya","Radha","Komal",
                "Preeti","Jyoti","Manju"]
LAST_NAMES = ["Mehta","Malhotra","Sharma","Verma","Bhatia","Kapoor","Khanna","Sethi",
              "Yadav","Chawla","Gupta","Arora","Singh","Rathore","Chopra","Bansal",
              "Aggarwal","Joshi","Nair","Iyer","Reddy","Choudhary","Saxena","Tiwari",
              "Pandey","Mishra","Rawat","Bhalla","Kohli","Grover"]

OCCUPATIONS = ["Trader","Logistics Manager","Accountant","Shop Owner","IT Consultant",
               "Transporter","Real Estate Agent","Bank Employee","Salesperson",
               "Small Business Owner","Driver","Clerk","Freelance Consultant",
               "Warehouse Supervisor","Retailer"]

ORG_TYPES = ["logistics","transport","trading","consulting","manufacturing","retail",
             "technology","finance","construction"]
ORG_NAME_TEMPLATES = ["{name} {suffix}", "{name} & Sons {suffix}", "{name} Group {suffix}"]
ORG_SUFFIX = {"logistics":"Logistics Pvt Ltd","transport":"Transport Services",
              "trading":"Trading Co","consulting":"Consulting Services",
              "manufacturing":"Manufacturing Ltd","retail":"Retail Stores",
              "technology":"Technologies Pvt Ltd","finance":"Finance Services",
              "construction":"Constructions Pvt Ltd"}

BANK_NAMES = ["National Cooperative Bank","Bharat Urban Bank","Saraswati Finance Bank",
              "Vindhya Rural Bank","Himgiri Commercial Bank","Suvidha Nagrik Bank"]

VEHICLE_TYPES = ["Car","Motorcycle","SUV","Van","Pickup Truck"]
VEHICLE_MAKES = {"Car":["Maruti Suzuki","Hyundai","Tata","Honda"],
                 "Motorcycle":["Hero","Bajaj","TVS","Royal Enfield"],
                 "SUV":["Mahindra","Tata","Toyota"],
                 "Van":["Maruti Suzuki","Tata","Force"],
                 "Pickup Truck":["Tata","Ashok Leyland","Mahindra"]}
VEHICLE_MODELS = {"Maruti Suzuki":["Swift","Dzire","Ertiga"],"Hyundai":["i20","Creta","Venue"],
                   "Tata":["Nexon","Tiago","Ace"],"Honda":["City","Amaze"],
                   "Hero":["Splendor","Passion"],"Bajaj":["Pulsar","Platina"],
                   "TVS":["Apache","Star City"],"Royal Enfield":["Classic 350","Bullet"],
                   "Mahindra":["Scorpio","Bolero","XUV500"],"Toyota":["Innova","Fortuner"],
                   "Force":["Traveller"],"Ashok Leyland":["Dost"]}
VEHICLE_COLORS = ["White","Silver","Black","Grey","Red","Blue"]

ROLES = ["Coordinator","Financial Intermediary","Recruiter","Logistics Coordinator",
         "Communicator","Document Handler","Vehicle Provider","Organization Owner",
         "Middleman","Operational Member","Associate","Witness","Victim",
         "Unrelated Person","False Lead"]

DOCUMENT_TYPES = ["FIR", "Witness Statement", "Investigation Note",
                   "Surveillance Summary", "Call Analysis Summary",
                   "Vehicle Observation Report", "Transaction Summary"]
