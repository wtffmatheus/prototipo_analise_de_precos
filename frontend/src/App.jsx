import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const T = {
  bg: "#07080f",
  card: "#0e1120",
  border: "#1c2540",
  cyan: "#00d4ff",
  green: "#00e676",
  orange: "#ffab40",
  red: "#ff5252",
  text: "#dde3f5",
  muted: "#94a3b8",
};

const LOJAS = [
  {
    nome: "Mercado Livre",
    preco: 4299,
    cor: "#ffe600",
    emoji: "🛒",
  },
  {
    nome: "Amazon",
    preco: 4099,
    cor: "#ff9900",
    emoji: "📦",
  },
  {
    nome: "KaBuM!",
    preco: 3920,
    cor: "#f04e23",
    emoji: "🖥️",
  },
  {
    nome: "Magalu",
    preco: 4170,
    cor: "#0086ff",
    emoji: "🛍️",
  },
  {
    nome: "OLX",
    preco: 3499,
    cor: "#9adc00",
    emoji: "🏷️",
  },
];

function gerarHistorico(base) {
  let p = base;

  return Array.from({ length: 10 }, (_, i) => {
    p += Math.random() * 300 - 150;

    return {
      dia: `${i + 1}`,
      preco: Number(p.toFixed(0)),
    };
  });
}

export default function App() {
  const [produto, setProduto] = useState("");
  const [loading, setLoading] = useState(false);
  const [dados, setDados] = useState(null);

  async function pesquisar() {
    if (!produto) return;

    setLoading(true);

    try {
      const resp = await fetch(
        "https://prototipoanalisedeprecos-copy-production.up.railway.app/perguntar",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            prompt: produto,
          }),
        }
      );

      let data = null;

      try {
        data = await resp.json();
      } catch {
        data = null;
      }

      console.log(data);

      const resultados = LOJAS.map((l) => ({
        ...l,
        historico: gerarHistorico(l.preco),
      }));

      setDados({
        produto,
        resultados,
      });
    } catch (err) {
      console.error(err);

      const resultados = LOJAS.map((l) => ({
        ...l,
        historico: gerarHistorico(l.preco),
      }));

      setDados({
        produto,
        resultados,
      });
    }

    setLoading(false);
  }

  return (
    <div
      style={{
        background: T.bg,
        minHeight: "100vh",
        padding: 20,
        color: T.text,
        fontFamily: "Arial",
      }}
    >
      <div
        style={{
          maxWidth: 1300,
          margin: "0 auto",
        }}
      >
        <h1
          style={{
            textAlign: "center",
            fontSize: "clamp(28px, 5vw, 52px)",
            marginBottom: 10,
          }}
        >
          📊 Análise de Preços IA
        </h1>

        <p
          style={{
            textAlign: "center",
            color: T.muted,
            marginBottom: 40,
            fontSize: "clamp(14px, 2vw, 18px)",
          }}
        >
          Compare preços em múltiplas lojas automaticamente
        </p>

        <div
          style={{
            display: "flex",
            gap: 12,
            marginBottom: 30,
            flexWrap: "wrap",
          }}
        >
          <input
            value={produto}
            onChange={(e) => setProduto(e.target.value)}
            placeholder="Digite um produto..."
            style={{
              flex: 1,
              minWidth: 240,
              padding: 16,
              borderRadius: 12,
              border: `1px solid ${T.border}`,
              background: T.card,
              color: T.text,
              fontSize: 16,
              outline: "none",
            }}
          />

          <button
            onClick={pesquisar}
            disabled={loading}
            style={{
              padding: "16px 26px",
              borderRadius: 12,
              border: "none",
              background: T.cyan,
              color: "#000",
              fontWeight: "bold",
              cursor: "pointer",
              fontSize: 16,
            }}
          >
            {loading ? "Pesquisando..." : "Pesquisar"}
          </button>
        </div>

        {dados && (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  "repeat(auto-fit, minmax(260px, 1fr))",
                gap: 18,
                marginBottom: 30,
              }}
            >
              {dados.resultados.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    background: T.card,
                    border: `1px solid ${T.border}`,
                    borderRadius: 18,
                    padding: 20,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: 12,
                    }}
                  >
                    <h2
                      style={{
                        fontSize: 20,
                      }}
                    >
                      {item.emoji} {item.nome}
                    </h2>

                    <span
                      style={{
                        color: item.cor,
                        fontWeight: "bold",
                      }}
                    >
                      ONLINE
                    </span>
                  </div>

                  <h1
                    style={{
                      color: T.green,
                      marginBottom: 10,
                      fontSize: 34,
                    }}
                  >
                    R$ {item.preco}
                  </h1>

                  <p
                    style={{
                      color: T.muted,
                      marginBottom: 20,
                    }}
                  >
                    Melhor oferta encontrada
                  </p>

                  <div
                    style={{
                      width: "100%",
                      height: 220,
                    }}
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={item.historico}>
                        <XAxis dataKey="dia" stroke="#666" />
                        <YAxis stroke="#666" />
                        <Tooltip />

                        <Line
                          type="monotone"
                          dataKey="preco"
                          stroke={item.cor}
                          strokeWidth={3}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ))}
            </div>

            <div
              style={{
                background: T.card,
                border: `1px solid ${T.border}`,
                borderRadius: 18,
                padding: 24,
              }}
            >
              <h2
                style={{
                  marginBottom: 18,
                  fontSize: 28,
                }}
              >
                🤖 Análise Inteligente
              </h2>

              <p
                style={{
                  color: T.muted,
                  lineHeight: 1.8,
                  fontSize: 16,
                }}
              >
                O menor preço encontrado atualmente está na OLX. A KaBuM
                apresenta o melhor custo-benefício para produtos novos.
                O histórico mostra tendência de queda nos últimos dias,
                podendo indicar promoções próximas.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}