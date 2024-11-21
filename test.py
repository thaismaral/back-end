import pytest
from fastapi.testclient import TestClient
from index import app

client = TestClient(app)

def test_criar_categoria():
    nova_categoria = {"nome": "Remédios"}
    response = client.post("/categorias/", json=nova_categoria)
    assert response.status_code == 200
    dados = response.json()
    assert "id" in dados
    assert dados["nome"] == nova_categoria["nome"]

def test_excluir_categoria_com_produtos_associados():
    categoria_response = client.post("/categorias/", json={"nome": "Gaiolas"})
    assert categoria_response.status_code == 200
    categoria_id = categoria_response.json()["id"]

    client.post(
        "/produtos/",
        json={
            "nome": "Gaiolas de passarinho",
            "preco": 999.99,
            "quantidade_estoque": 5,
            "categoria_id": categoria_id,
        },
    )
    response = client.delete(f"/categorias/{categoria_id}")
    assert response.status_code == 400
    assert response.json()["detail"] == "Não é possível excluir categorias com produtos associados"

def test_criar_produto():
    categoria_response = client.post("/categorias/", json={"nome": "Brinquedos"})
    assert categoria_response.status_code == 200
    categoria_id = categoria_response.json()["id"]
    novo_produto = {
        "nome": "Bola",
        "preco": 29.90,
        "quantidade_estoque": 10,
        "categoria_id": categoria_id,
    }
    response = client.post("/produtos/", json=novo_produto)
    assert response.status_code == 200
    dados = response.json()
    assert "id" in dados
    assert dados["nome"] == novo_produto["nome"]
    assert dados["preco"] == novo_produto["preco"]
    assert dados["quantidade_estoque"] == novo_produto["quantidade_estoque"]
    assert dados["categoria_id"] == novo_produto["categoria_id"]

def test_criar_pedido():
    categoria_response = client.post("/categorias/", json={"nome": "Roupa"})
    assert categoria_response.status_code == 200
    categoria_id = categoria_response.json()["id"]
    produto_response = client.post(
        "/produtos/",
        json={
            "nome": "Gatinhos Quentinhos",
            "preco": 50,
            "quantidade_estoque": 10,
            "categoria_id": categoria_id,
        },
    )
    assert produto_response.status_code == 200
    produto_id = produto_response.json()["id"]
    pedido_data = {
        "produto_id": produto_id,
        "quantidade": 10,
    }
    pedido_response = client.post("/pedidos/", json=pedido_data)
    assert pedido_response.status_code == 200

    dados = pedido_response.json()
    assert "id" in dados
    assert dados["produto_id"] == pedido_data["produto_id"]
    assert dados["quantidade"] == pedido_data["quantidade"]
    assert "data" in dados  

def test_criar_pedido_com_estoque_insuficiente():
    categoria_response = client.post("/categorias/", json={"nome": "Camas"})
    assert categoria_response.status_code == 200
    categoria_id = categoria_response.json()["id"]
    produto_response = client.post(
        "/produtos/",
        json={
            "nome": "Cama peluciada",
            "preco": 100,
            "quantidade_estoque": 5,
            "categoria_id": categoria_id,
        },
    )
    assert produto_response.status_code == 200
    produto_id = produto_response.json()["id"]
    pedido_data = {
        "produto_id": produto_id,
        "quantidade": 10, 
    }
    response = client.post("/pedidos/", json=pedido_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "Quantidade em estoque insuficiente"
