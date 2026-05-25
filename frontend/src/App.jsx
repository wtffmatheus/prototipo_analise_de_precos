import { useState } from "react";

const T = {
  bg: "#07080f",
  card: "#141828",
  cyan: "#00d4ff",
  green: "#00e676",
  text: "#dde3f5",
  muted: "#94a3b8",
};

async function buscarPrecosIA(nome, meta) {
  const precoBase = Math.floor(Math.random() * 4000) + 1000;

  const resultados = [
    {
      loja_id: "Mercado Livre",
      preco: precoBase,
      frete: "Grátis",
      condicao: "Novo",
      url: "https://mercadolivre.com.br",
    },
    {
      loja_id: "Amazon",
      preco: precoBase - 120,
      frete: "Prime",
      condicao: "Novo",
      url: "https://amazon.com.br",
    },
    {
      loja_id: "KaBuM!",
      preco: precoBase - 250,
      frete: "Grátis",
      condicao: "Novo",
      url: "https://kabum.com.br",
    },
    {
      loja_id: "Magalu",
      preco: precoBase - 80,
      frete: "Grátis",
      condicao: "Novo",
      url: "https://magazineluiza.com.br",
    },
    {
      loja_id: "OLX",
      preco: precoBase - 600,
      frete: "Combinar",
      condicao: "Usado",
      url: "https://olx.com.br",
    },
    {
      loja_id: "Enjoei",
      preco: precoBase - 500,
      frete: "R$ 20",
      condicao: "Seminovo",
      url: "https://enjoei.com.br",
    },
  ];

  return {
    produto_normalizado: nome,
    resultados,
    analise:
      precoBase <= meta
        ? "O preço atual está abaixo da meta. Vale a pena comprar agora."
        : "Os preços ainda estão acima da meta. Talvez seja melhor esperar promoções.",
  };
}

export default function App() {
  const [produto, setProduto] = useState("");
  const [meta, setMeta] = useState("");
  const [dados, setDados] = useState(null);
  const [loading, setLoading] = useState(false);

  async function buscar() {
    if (!produto || !meta) return;

    setLoading(true);

    try {
      const res = await buscarPrecosIA(produto, Number(meta));
      setDados(res);
    } catch (e) {
      console.error(e);
      alert("Erro ao buscar preços");
    }

    setLoading(false);
  }

  return (
    <div
      style={{
        background: T.bg,
        minHeight: "100vh",
        padding: 40,
        fontFamily: "Arial",
        color: T.text,
      }}
    >
      <h1
        style={{
          color: T.cyan,
          fontSize: 42,
          marginBottom: 10,
        }}
      >
        🎯 Monitor de Preços
      </h1>

      <p
        style={{
          color: T.muted,
          marginBottom: 30,
        }}
      >
        Compare preços automaticamente entre lojas
      </p>

      <div
        style={{
          display: "flex",
          gap: 12,
          marginBottom: 25,
          flexWrap: "wrap",
        }}
      >
        <input
          placeholder="Produto"
          value={produto}
          onChange={(e) => setProduto(e.target.value)}
          style={{
            padding: 14,
            borderRadius: 10,
            border: "1px solid #1e293b",
            background: "#0e1120",
            color: "white",
            minWidth: 250,
          }}
        />

        <input
          placeholder="Preço meta"
          type="number"
          value={meta}
          onChange={(e) => setMeta(e.target.value)}
          style={{
            padding: 14,
            borderRadius: 10,
            border: "1px solid #1e293b",
            background: "#0e1120",
            color: "white",
            width: 180,
          }}
        />

        <button
          onClick={buscar}
          style={{
            background: T.cyan,
            color: "#000",
            border: "none",
            borderRadius: 10,
            padding: "14px 24px",
            fontWeight: "bold",
            cursor: "pointer",
          }}
        >
          {loading ? "Buscando..." : "Buscar"}
        </button>
      </div>

      {dados && (
        <>
          <h2
            style={{
              marginBottom: 20,
            }}
          >
            Resultados para: {dados.produto_normalizado}
          </h2>

          <div
            style={{
              display: "grid",
              gap: 16,
            }}
          >
            {dados.resultados.map((r, index) => (
              <div
                key={index}
                style={{
                  background: T.card,
                  padding: 20,
                  borderRadius: 16,
                  border: "1px solid #1e293b",
                }}
              >
                <h3
                  style={{
                    marginTop: 0,
                  }}
                >
                  {r.loja_id}
                </h3>

                <div
                  style={{
                    fontSize: 30,
                    color: T.green,
                    fontWeight: "bold",
                    marginBottom: 10,
                  }}
                >
                  R$ {r.preco}
                </div>

                <p>Condição: {r.condicao}</p>
                <p>Frete: {r.frete}</p>

                <a
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    color: T.cyan,
                    textDecoration: "none",
                    fontWeight: "bold",
                  }}
                >
                  Ver loja →
                </a>
              </div>
            ))}
          </div>

          <div
            style={{
              marginTop: 30,
              background: "#0e1120",
              padding: 20,
              borderRadius: 16,
              border: "1px solid #1e293b",
            }}
          >
            <h3
              style={{
                color: T.cyan,
                marginTop: 0,
              }}
            >
              🤖 Análise
            </h3>

            <p
              style={{
                lineHeight: 1.6,
              }}
            >
              {dados.analise}
            </p>
          </div>
        </>
      )}
    </div>
  );
}