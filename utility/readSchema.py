def readHcpPatientsSchema():
    with open('data/schemas/HcpPatients.txt', 'r') as file:
        content = file.read()
    return content

def readPoliceForceSchema():
    with open('data/schemas/PoliceForce.txt', 'r') as file:
        content = file.read()
    return content
