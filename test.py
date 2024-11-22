import pytest
from fastapi.testclient import TestClient
from index import app

client = TestClient(app)

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
