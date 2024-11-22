from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import jwt
import logging
from datetime import datetime, timedelta

DATABASE_URL = "test.db"
SECRET_KEY = "trabalhoBackEnd"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

def criar_tabelas():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            quantidade_estoque INTEGER NOT NULL,  -- Inclui estoque
            categoria_id INTEGER,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedido_produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)
    
    conn.commit()
    conn.close()

class CategoriaBase(BaseModel):
    nome: str

class Categoria(CategoriaBase):
    id: int

    class Config:
        from_attributes = True

class ProdutoBase(BaseModel):
    nome: str
    preco: float
    quantidade_estoque: int  
    categoria_id: int

class Produto(ProdutoBase):
    id: int

    class Config:
        from_attributes = True

class PedidoProduto(BaseModel):
    produto_id: int
    quantidade: int

class PedidoBase(BaseModel):
    produtos: List[PedidoProduto]

class Pedido(PedidoBase):
    id: int
    data: str
    valor_total: float

    class Config:
        from_attributes = True

criar_tabelas()

def criar_token(dados: dict):
    try:
        dados_a_serem_codificados = dados.copy()
        expiracao = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        dados_a_serem_codificados.update({"exp": expiracao})
        token = jwt.encode(dados_a_serem_codificados, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"Token criado: {token}")
        return token
    except Exception as e:
        logger.error(f"Erro ao criar o token: {e}")
        raise HTTPException(status_code=500, detail="Erro ao criar o token")
    
def verificar_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        logger.info(f"Tentativa de login com username: {form_data.username}")
        if form_data.username != "thais" or form_data.password != "2005":
            logger.warning("Credenciais inválidas")
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        access_token = criar_token({"sub": form_data.username})
        logger.info("Token gerado com sucesso")
        return {"access_token": access_token, "token_type": "bearer"}
    except jwt.ExpiredSignatureError:
        logger.error("Erro: Token expirado")
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        logger.error("Erro: Token inválido")
        raise HTTPException(status_code=401, detail="Token inválido")
    except Exception as e:
        logger.error(f"Erro interno: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao processar a requisição")

@app.post("/categorias/", response_model=Categoria)
def criar_categoria(categoria: CategoriaBase):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categorias (nome) VALUES (?)", (categoria.nome,))
    conn.commit()
    categoria_id = cursor.lastrowid
    conn.close()
    logger.info(f"Categoria criada: ID {categoria_id}, Nome {categoria.nome}")
    return Categoria(id=categoria_id, nome=categoria.nome)

@app.get("/categorias/", response_model=List[Categoria])
def listar_categorias():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categorias")
    rows = cursor.fetchall()
    conn.close()
    return [Categoria(id=row["id"], nome=row["nome"]) for row in rows]

@app.delete("/categorias/{categoria_id}")
def deletar_categoria(categoria_id: int, token: str = Depends(verificar_token)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM categorias WHERE id = ?", (categoria_id,))
        categoria = cursor.fetchone()
        if not categoria:
            raise HTTPException(status_code=404, detail="Categoria não encontrada")
        cursor.execute("SELECT * FROM produtos WHERE categoria_id = ?", (categoria_id,))
        produtos = cursor.fetchall()
        if produtos:
            raise HTTPException(status_code=400, detail="Não é possível excluir categorias com produtos associados")
        cursor.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Categoria não encontrada")
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir a categoria: {str(e)}")
    finally:
        conn.close()
    logger.info(f"Categoria excluída: ID {categoria_id}")
    return {"message": "Categoria excluída com sucesso"}


@app.post("/produtos/", response_model=Produto)
def criar_produto(produto: ProdutoBase):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM categorias WHERE id = ?", (produto.categoria_id,))
        categoria = cursor.fetchone()
        if not categoria:
            raise HTTPException(status_code=404, detail="Categoria não encontrada")
        cursor.execute(
            """
            INSERT INTO produtos (nome, preco, quantidade_estoque, categoria_id)
            VALUES (?, ?, ?, ?)
            """,
            (produto.nome, produto.preco, produto.quantidade_estoque, produto.categoria_id),
        )
        conn.commit()
        produto_id = cursor.lastrowid
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar o produto: {str(e)}")
    finally:
        conn.close()
    logger.info(f"Produto criado: ID {produto_id}, Nome {produto.nome}")
    return Produto(
        id=produto_id,
        nome=produto.nome,
        preco=produto.preco,
        quantidade_estoque=produto.quantidade_estoque,
        categoria_id=produto.categoria_id,
    )
@app.get("/produtos/{produto_id}", response_model=Produto)
def obter_produto(produto_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return Produto(
        id=row["id"],
        nome=row["nome"],
        preco=row["preco"],
        quantidade_estoque=row["quantidade_estoque"],
        categoria_id=row["categoria_id"]
    )

@app.get("/produtos/", response_model=List[Produto])
def listar_produtos():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM produtos")
    rows = cursor.fetchall()
    conn.close()
    return [
        Produto(
            id=row["id"],
            nome=row["nome"],
            preco=row["preco"],
            quantidade_estoque=row["quantidade_estoque"],
            categoria_id=row["categoria_id"]
        )
        for row in rows
    ]

@app.get("/produtos/buscar/", response_model=List[Produto])
def buscar_produto(
    nome: str = Query(None, description="Nome ou parte do nome do produto"),
    ordenar_por: Optional[str] = Query("nome", description="Campo para ordenação (nome, preco, quantidade_estoque)"),
    direcao: Optional[str] = Query("asc", description="Direção da ordenação (asc ou desc)")
):
    if ordenar_por not in ["nome", "preco", "quantidade_estoque"]:
        raise HTTPException(status_code=400, detail="Campo de ordenação inválido")
    if direcao not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Direção de ordenação inválida")
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM produtos"
    params = []
    if nome:
        query += " WHERE nome LIKE ?"
        params.append(f"%{nome}%")
    query += f" ORDER BY {ordenar_por} {direcao.upper()}"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="Nenhum produto encontrado")
    return [
        Produto(
            id=row["id"],
            nome=row["nome"],
            preco=row["preco"],
            quantidade_estoque=row["quantidade_estoque"],
            categoria_id=row["categoria_id"]
        )
        for row in rows
    ]


@app.put("/produtos/{produto_id}", response_model=Produto)
def atualizar_produto(produto_id: int, produto: ProdutoBase):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM categorias WHERE id = ?", (produto.categoria_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Categoria não encontrada")
        cursor.execute(
            """
            UPDATE produtos
            SET nome = ?, preco = ?, quantidade_estoque = ?, categoria_id = ?
            WHERE id = ?
            """,
            (produto.nome, produto.preco, produto.quantidade_estoque, produto.categoria_id, produto_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar o produto: {str(e)}")
    finally:
        conn.close()
    logger.info(f"Produto atualizado: ID {produto_id}")
    return Produto(
        id=produto_id,
        nome=produto.nome,
        preco=produto.preco,
        quantidade_estoque=produto.quantidade_estoque,
        categoria_id=produto.categoria_id,
    )

@app.delete("/produtos/{produto_id}")
def deletar_produto(produto_id: int, token: str = Depends(verificar_token)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    conn.commit()
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    conn.close()
    logger.info(f"Produto deletado: ID {produto_id}")
    return {"message": "Produto removido com sucesso"}

@app.post("/pedidos/", response_model=Pedido)
def criar_pedido(pedido: PedidoBase):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO pedidos (data) VALUES (?)", (datetime.utcnow().isoformat(),))
        pedido_id = cursor.lastrowid
        valor_total = 0
        for item in pedido.produtos:
            cursor.execute("SELECT preco, quantidade_estoque FROM produtos WHERE id = ?", (item.produto_id,))
            produto = cursor.fetchone()
            if not produto:
                raise HTTPException(status_code=404, detail=f"Produto ID {item.produto_id} não encontrado")
            if produto["quantidade_estoque"] < item.quantidade:
                raise HTTPException(status_code=400, detail=f"Estoque insuficiente para o produto ID {item.produto_id}")
            valor_total += produto["preco"] * item.quantidade
            cursor.execute(
                "INSERT INTO pedido_produtos (pedido_id, produto_id, quantidade) VALUES (?, ?, ?)",
                (pedido_id, item.produto_id, item.quantidade)
            )
            cursor.execute(
                "UPDATE produtos SET quantidade_estoque = quantidade_estoque - ? WHERE id = ?",
                (item.quantidade, item.produto_id)
            )
        conn.commit()
        logger.info(f"Pedido criado com sucesso: ID {pedido_id}, Valor Total {valor_total}")
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Erro no banco de dados ao criar o pedido: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro no banco de dados: {str(e)}")
    finally:
        conn.close()
    return Pedido(
        id=pedido_id,
        data=datetime.utcnow().isoformat(),
        produtos=pedido.produtos,
        valor_total=valor_total,
    )

@app.get("/pedidos/", response_model=List[Pedido])
def listar_pedidos():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT p.id as pedido_id, p.data, pp.produto_id, pp.quantidade, pr.nome, pr.preco
            FROM pedidos p
            LEFT JOIN pedido_produtos pp ON p.id = pp.pedido_id
            LEFT JOIN produtos pr ON pp.produto_id = pr.id
            ORDER BY p.id
        """)
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="Nenhum pedido encontrado")
        pedidos = {}
        for row in rows:
            pedido_id = row["pedido_id"]
            if pedido_id not in pedidos:
                pedidos[pedido_id] = {
                    "id": pedido_id,
                    "data": row["data"],
                    "produtos": [],
                    "valor_total": 0
                }
            if row["produto_id"]:
                produto_info = {
                    "produto_id": row["produto_id"],
                    "quantidade": row["quantidade"],
                    "nome": row["nome"],
                    "preco": row["preco"]
                }
                pedidos[pedido_id]["produtos"].append(produto_info)
                pedidos[pedido_id]["valor_total"] += row["quantidade"] * row["preco"]

        return list(pedidos.values())
    finally:
        conn.close()


@app.get("/pedidos/{pedido_id}", response_model=Pedido)
def obter_pedido(pedido_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT p.id as pedido_id, p.data, pp.produto_id, pp.quantidade, pr.nome, pr.preco
            FROM pedidos p
            LEFT JOIN pedido_produtos pp ON p.id = pp.pedido_id
            LEFT JOIN produtos pr ON pp.produto_id = pr.id
            WHERE p.id = ?
        """, (pedido_id,))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        pedido = {
            "id": pedido_id,
            "data": rows[0]["data"],
            "produtos": [],
            "valor_total": 0
        }
        for row in rows:
            if row["produto_id"]:
                produto_info = {
                    "produto_id": row["produto_id"],
                    "quantidade": row["quantidade"],
                    "nome": row["nome"],
                    "preco": row["preco"]
                }
                pedido["produtos"].append(produto_info)
                pedido["valor_total"] += row["quantidade"] * row["preco"]
        return pedido
    finally:
        conn.close()

@app.delete("/pedidos/{pedido_id}")
def deletar_pedido(pedido_id: int, token: str = Depends(verificar_token)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,))
        pedido = cursor.fetchone()
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        cursor.execute("DELETE FROM pedido_produtos WHERE pedido_id = ?", (pedido_id,))
        cursor.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
        conn.commit()
        logger.info(f"Pedido deletado: ID {pedido_id}")
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Erro ao excluir o pedido: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao excluir o pedido: {str(e)}")
    finally:
        conn.close()
    return {"message": "Pedido removido com sucesso"}
