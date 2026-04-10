def test_create_project_valid(client, auth_headers):
    response = client.post("/projects/", json={"name": "Test Project", "description": "A test project"}, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["description"] == "A test project"

def test_create_project_duplicate_name(client, auth_headers):
    response1 = client.post("/projects/", json={"name": "Test Project", "description": "First project"}, headers=auth_headers)
    assert response1.status_code == 201
    response2 = client.post("/projects/", json={"name": "Test Project", "description": "Second project"}, headers=auth_headers)
    assert response2.status_code == 201
    data2 = response2.json()
    assert data2["name"] == "Test Project (1)"

def test_create_project_duplicate_name_multiple(client, auth_headers):
    client.post("/projects/", json={"name": "Test Project", "description": "First project"}, headers=auth_headers)
    client.post("/projects/", json={"name": "Test Project", "description": "Second project"}, headers=auth_headers)
    response3 = client.post("/projects/", json={"name": "Test Project", "description": "Third project"}, headers=auth_headers)
    assert response3.status_code == 201
    data3 = response3.json()
    assert data3["name"] == "Test Project (2)"

def test_create_project_empty_description(client, auth_headers):
    response = client.post("/projects/", json={"name": "Project with empty description", "description": ""}, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Project with empty description"
    assert data["description"] == ""

def test_create_project_empty_name(client, auth_headers):
    response = client.post("/projects/", json={"name": "", "description": "No name"}, headers=auth_headers)
    assert response.status_code == 422

def test_create_project_name_with_spaces(client, auth_headers):
    response = client.post("/projects/", json={"name": "    ", "description": "Name with only spaces"}, headers=auth_headers)
    assert response.status_code == 422

def test_create_project_name_with_one_character(client, auth_headers):
    response = client.post("/projects/", json={"name": "A", "description": "Name with one character"}, headers=auth_headers)
    assert response.status_code == 422