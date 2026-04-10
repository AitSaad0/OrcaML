def test_create_project_valid(client): 
    response = client.post("/projects/", json={"name": "Test Project", "description": "A test project"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["description"] == "A test project"


def test_create_project_duplicate_name(client):
    response1 = client.post("/projects/", json={"name": "Test Project", "description": "First project"})
    assert response1.status_code == 201

    response2 = client.post("/projects/", json={"name": "Test Project", "description": "Second project"})
    assert response2.status_code == 201
    data2 = response2.json()
    assert data2["name"] == "Test Project (1)"


def test_create_project_duplicate_name_multiple(client):
    client.post("/projects/", json={"name": "Test Project", "description": "First project"})
    client.post("/projects/", json={"name": "Test Project", "description": "Second project"})
    response3 = client.post("/projects/", json={"name": "Test Project", "description": "Third project"})
    assert response3.status_code == 201
    data3 = response3.json()
    assert data3["name"] == "Test Project (2)"

def test_create_project_empty_description(client):
    response = client.post("/projects/", json={"name": "Project with empty description", "description": ""})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Project with empty description"
    assert data["description"] == ""


def test_create_project_empty_name(client):
    response = client.post("/projects/", json={"name": "", "description": "No name"})
    assert response.status_code == 422 

def test_create_project_name_with_spaces(client):
    response = client.post("/projects/", json={"name": "    ", "description": "Name with only spaces"})
    assert response.status_code == 422

def test_create_project_name_with_one_character(client):
    response = client.post("/projects/", json={"name": "A", "description": "Name with one character"})
    assert response.status_code == 422
