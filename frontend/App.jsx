import { useEffect, useMemo, useRef, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

const API_URL = "https://prototipoanalisedeprecos-copy-production.up.railway.app";

const T = {
  bg: "#07080f",
  card: "#0e1120",
  cardAlt: "#141828",
  border: "#1c2540",
  cyan: "#00d4ff",
  cyanDim: "#00d4ff18",
  green: "#00e676",
  greenDim: "#00e67618",
  orange: "#ffab40",
  red: "#ff5252",
  text: "#dde3f5",
  muted: "#7b88a8",
  dim: "#4a5568",
};

function formatarMoeda(valor) {
  return Number(valor || 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function gerarHistorico(base, dias = 21) {
  let preco = Number(base || 1000) * 1.1;
  const hoje = new Date();

  return Array.from({ length: dias }, (_, i) => {
    preco *= 1 + (Math.random() * 0.07 - 0.035);

    const data = new Date(hoje);
    data.setDate(data.getDate() - (dias - 1 - i));

    return {
      data: data.toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
      }),
      preco: Number(preco.toFixed(2)),
    };
  });
}

const lojaInfo = {
  mercadolivre: { nome: "Mercado Livre", cor: "#ffe600", bg: "#ffe60015", emoji: "🛒" },
  amazon: { nome: "Amazon", cor: "#ff9900", bg: "#ff990015", emoji: "📦" },
  kabum: { nome: "KaBuM!", cor: "#f04e23", bg: "#f04e2315", emoji: "🖥️" },
  magalu: { nome: "Magalu", cor: "#0086ff", bg: "#0086ff15", emoji: "🛍️" },
  olx: { nome: "OLX", cor: "#9adc00", bg: "#9adc0015", emoji: "🏷️" },
  enjoei: { nome: "Enjoei", cor: "#ff69b4", bg: "#ff69b415", emoji: "✨" },
};

const Chip = ({ children, color = T.cyan, bg, style = {} }) => (
  <span
    style={{
      background: bg || `${color}20`,
      color,
      fontSize: 11,
      fontWeight: 800,
      padding: "4px 9px",
      borderRadius: 999,
      border: `1px solid ${color}35`,
      whiteSpace: "nowrap",
      ...style,
    }}
  >
    {children}
  </span>
);

function LojaTag({ id, nome }) {
  const loja = lojaInfo[id] || { nome: nome || id, cor: T.cyan, bg: T.cyanDim, emoji: "🏬" };

  return (
    <Chip color={loja.cor} bg={loja.bg}>
      {loja.emoji} {loja.nome}
    </Chip>
  );
}

function TooltipChart({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div
      style={{
        background: T.card,
        border: `1px solid ${T.border}`,
        borderRadius: 10,
        padding: "9px 12px",
        fontSize: 12,
      }}
    >
      <div style={{ color: T.muted }}>{label}</div>
      <div style={{ color: T.cyan, fontWeight: 800 }}>
        {formatarMoeda(payload[0].value)}
      </div>
    </div>
  );
}

function TelaBusca({ onBuscar, carregando, erro }) {
  const [nome, setNome] = useState("");
  const [meta, setMeta] = useState("");
  const [email, setEmail] = useState("");
  const [proximidade, setProximidade] = useState(10);
  const [aceitaUsado, setAceitaUsado] = useState(true);
  const [aceitaNovo, setAceitaNovo] = useState(true);
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const podeBuscar = nome.trim() && meta && Number(meta) > 0 && !carregando;

  const inputStyle = {
    width: "100%",
    boxSizing: "border-box",
    background: T.bg,
    border: `1.5px solid ${T.border}`,
    borderRadius: 13,
    padding: "14px 15px",
    color: T.text,
    fontSize: 15,
    outline: "none",
    marginBottom: 15,
  };

  const labelStyle = {
    fontSize: 11,
    fontWeight: 900,
    color: T.muted,
    textTransform: "uppercase",
    letterSpacing: 1,
    display: "block",
    marginBottom: 7,
  };

  function enviarBusca() {
    if (!podeBuscar) return;

    onBuscar({
      nome: nome.trim(),
      meta: Number(meta),
      email: email.trim(),
      proximidade: Number(proximidade || 10),
      aceitaUsado,
      aceitaNovo,
    });
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: T.bg,
        color: T.text,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 18,
        fontFamily: "'Inter', 'Segoe UI', Arial, sans-serif",
      }}
    >
      <div style={{ width: "100%", maxWidth: 520, position: "relative" }}>
        <div
          style={{
            textAlign: "center",
            marginBottom: 28,
            position: "relative",
          }}
        >
          <div style={{ fontSize: 48, marginBottom: 8 }}>🎯</div>

          <h1
            style={{
              margin: 0,
              fontSize: "clamp(30px, 8vw, 46px)",
              fontWeight: 950,
              letterSpacing: -1.5,
            }}
          >
            Monitor de <span style={{ color: T.cyan }}>Preços</span>
          </h1>

          <p style={{ color: T.muted, marginTop: 10, fontSize: 14 }}>
            Monitore produtos novos e usados, receba alerta por email e compare lojas.
          </p>
        </div>

        <div
          style={{
            background: T.card,
            border: `1px solid ${T.border}`,
            borderRadius: 24,
            padding: "clamp(18px, 5vw, 28px)",
            boxShadow: `0 0 90px ${T.cyan}12`,
          }}
        >
          <label style={labelStyle}>Produto</label>
          <input
            ref={inputRef}
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && enviarBusca()}
            placeholder="Ex: Ryzen 7 5700X, iPhone 15, RTX 4070..."
            style={inputStyle}
          />

          <label style={labelStyle}>Preço meta</label>
          <input
            value={meta}
            onChange={(e) => setMeta(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && enviarBusca()}
            placeholder="Ex: 950"
            type="number"
            style={inputStyle}
          />

          <label style={labelStyle}>Email para alerta</label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="seuemail@gmail.com"
            type="email"
            style={inputStyle}
          />

          <label style={labelStyle}>Alertar quando estiver até X% acima da meta</label>
          <input
            value={proximidade}
            onChange={(e) => setProximidade(e.target.value)}
            type="number"
            min="1"
            max="100"
            style={inputStyle}
          />

          <div
            style={{
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
              marginBottom: 16,
            }}
          >
            <label style={{ color: T.text, fontSize: 14 }}>
              <input
                type="checkbox"
                checked={aceitaNovo}
                onChange={(e) => setAceitaNovo(e.target.checked)}
              />{" "}
              Aceitar novo
            </label>

            <label style={{ color: T.text, fontSize: 14 }}>
              <input
                type="checkbox"
                checked={aceitaUsado}
                onChange={(e) => setAceitaUsado(e.target.checked)}
              />{" "}
              Aceitar usado/seminovo
            </label>
          </div>

          <button
            onClick={enviarBusca}
            disabled={!podeBuscar}
            style={{
              width: "100%",
              padding: "15px 0",
              background: podeBuscar
                ? `linear-gradient(135deg, ${T.cyan}, #007ea8)`
                : T.border,
              color: podeBuscar ? "#000" : T.dim,
              border: "none",
              borderRadius: 13,
              fontSize: 15,
              fontWeight: 950,
              cursor: podeBuscar ? "pointer" : "not-allowed",
            }}
          >
            {carregando ? "🔍 Buscando nas lojas..." : "🔍 Buscar e monitorar"}
          </button>

          {erro && (
            <div style={{ color: T.red, marginTop: 13, fontSize: 13, textAlign: "center" }}>
              {erro}
            </div>
          )}

          <p style={{ color: T.muted, fontSize: 12, lineHeight: 1.5, marginTop: 16 }}>
            Observação: cupons aparecem como estimativa. Confirme a validade no checkout da loja.
          </p>
        </div>
      </div>
    </div>
  );
}

function PainelResultado({ dados, meta, onNovaBusca }) {
  const [lojaAtiva, setLojaAtiva] = useState(null);
  const [aba, setAba] = useState("precos");

  // FIX: precoFinal sempre vem do preco_final do backend (nunca calculado aqui)
  // O backend garante preco_final == preco (cupons nunca alteram o preço)
  const resultados = useMemo(() => {
    return (dados.resultados || [])
      .map((r) => ({
        ...r,
        precoFinal: Number(r.preco_final ?? r.preco),
        historico: gerarHistorico(Number(r.preco_final ?? r.preco)),
      }))
      .sort((a, b) => a.precoFinal - b.precoFinal);
  }, [dados]);

  useEffect(() => {
    if (!lojaAtiva && resultados[0]) setLojaAtiva(resultados[0].loja_id);
  }, [resultados, lojaAtiva]);

  const ativo = resultados.find((r) => r.loja_id === lojaAtiva) || resultados[0];
  const lojaConf = lojaInfo[ativo?.loja_id] || { cor: T.cyan };

  const melhor = resultados[0];

  // FIX: label do botão de link baseado no link_tipo real do backend
  function labelLink(r) {
    return r.link_tipo === "busca" ? "Ver busca →" : "Ver produto →";
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: T.bg,
        color: T.text,
        padding: "clamp(12px, 3vw, 24px)",
        fontFamily: "'Inter', 'Segoe UI', Arial, sans-serif",
      }}
    >
      <div style={{ maxWidth: 1240, margin: "0 auto" }}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 14,
            alignItems: "flex-start",
            marginBottom: 18,
            flexWrap: "wrap",
          }}
        >
          <div>
            <div
              style={{
                fontSize: 11,
                color: T.muted,
                textTransform: "uppercase",
                letterSpacing: 1,
                fontWeight: 900,
              }}
            >
              🎯 Monitorando
            </div>

            <h1
              style={{
                margin: "4px 0",
                fontSize: "clamp(22px, 5vw, 36px)",
                letterSpacing: -1,
              }}
            >
              {dados.produto_normalizado}
            </h1>

            <div style={{ color: T.muted, fontSize: 14 }}>
              Meta: <b style={{ color: T.cyan }}>{formatarMoeda(meta)}</b>
              {dados.email && (
                <span style={{ marginLeft: 8 }}>
                  · alerta em <b>{dados.email}</b>
                </span>
              )}
            </div>
          </div>

          <button
            onClick={onNovaBusca}
            style={{
              background: T.cardAlt,
              color: T.text,
              border: `1px solid ${T.border}`,
              borderRadius: 12,
              padding: "10px 14px",
              fontWeight: 900,
              cursor: "pointer",
            }}
          >
            + Nova busca
          </button>
        </header>

        {resultados.length === 0 ? (
          <section
            style={{
              background: T.card,
              border: `1px solid ${T.border}`,
              borderRadius: 18,
              padding: 20,
            }}
          >
            <h2>Nenhum preço encontrado agora</h2>
            <p style={{ color: T.muted }}>{dados.analise}</p>
          </section>
        ) : (
          <>
            <section
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: 12,
                marginBottom: 16,
              }}
            >
              <Resumo label="Melhor preço" value={formatarMoeda(melhor?.precoFinal)} color={T.green} />
              <Resumo label="Loja destaque" value={melhor?.loja || "-"} />
              <Resumo label="Condição" value={melhor?.condicao || "-"} />
              <Resumo
                label="Status"
                value={melhor?.precoFinal <= meta ? "Dentro da meta" : "Monitorando"}
                color={melhor?.precoFinal <= meta ? T.green : T.orange}
              />
            </section>

            <div
              style={{
                display: "flex",
                gap: 6,
                background: T.card,
                border: `1px solid ${T.border}`,
                borderRadius: 14,
                padding: 5,
                marginBottom: 16,
              }}
            >
              {[
                { id: "precos", label: "💰 Preços" },
                { id: "cupons", label: "🎟️ Cupons estimados" },
              ].map((item) => (
                <button
                  key={item.id}
                  onClick={() => setAba(item.id)}
                  style={{
                    flex: 1,
                    padding: "10px 0",
                    borderRadius: 11,
                    border: "none",
                    background: aba === item.id ? T.cardAlt : "transparent",
                    color: aba === item.id ? T.text : T.muted,
                    fontWeight: 900,
                    cursor: "pointer",
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {aba === "precos" && (
              <div style={{ display: "grid", gap: 14 }}>
                <section
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(270px, 1fr))",
                    gap: 12,
                  }}
                >
                  {resultados.map((r, index) => {
                    const loja = lojaInfo[r.loja_id] || { cor: T.cyan, bg: T.cyanDim };
                    const atingiu = r.precoFinal <= meta;
                    const selecionada = lojaAtiva === r.loja_id;
                    const eBusca = r.link_tipo === "busca";

                    return (
                      <div
                        key={`${r.loja_id}-${index}`}
                        onClick={() => setLojaAtiva(r.loja_id)}
                        style={{
                          background: selecionada ? T.cardAlt : T.card,
                          border: `1.5px solid ${selecionada ? `${loja.cor}70` : T.border}`,
                          borderRadius: 18,
                          padding: 16,
                          color: T.text,
                          cursor: "pointer",
                          boxShadow: selecionada ? `0 0 24px ${loja.cor}16` : "none",
                        }}
                      >
                        <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginBottom: 9 }}>
                          <LojaTag id={r.loja_id} nome={r.loja} />
                          {index === 0 && <Chip color={T.green}>🏆 Melhor</Chip>}
                          {atingiu && <Chip color={T.green}>✅ Meta</Chip>}
                          {/* FIX: badge de busca para deixar claro ao usuário */}
                          {eBusca && (
                            <Chip color={T.orange}>🔍 Busca</Chip>
                          )}
                        </div>

                        <div
                          style={{
                            color: atingiu ? T.green : T.text,
                            fontSize: "clamp(24px, 6vw, 34px)",
                            fontWeight: 950,
                            marginBottom: 6,
                          }}
                        >
                          {formatarMoeda(r.precoFinal)}
                        </div>

                        {/* FIX: removido o bloco "Preço base" que comparava preco vs preco_final
                            e criava a falsa impressão de desconto aplicado.
                            O backend garante que preco_final == preco (cupons nunca alteram o preço). */}

                        <div style={{ color: T.muted, fontSize: 13 }}>
                          {r.condicao} · {r.titulo || "Produto encontrado"}
                        </div>

                        {r.melhor_cupom && (
                          <div style={{ marginTop: 7 }}>
                            <div style={{ color: T.orange, fontSize: 13 }}>
                              🎟️ Cupom estimado: <b>{r.melhor_cupom.codigo}</b>
                            </div>
                            <div style={{ color: T.muted, fontSize: 12, marginTop: 3 }}>
                              Não aplicado no preço — teste no checkout.
                            </div>
                          </div>
                        )}

                        <a
                          href={r.url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          style={{
                            display: "inline-block",
                            marginTop: 12,
                            color: "#000",
                            background: loja.cor || T.cyan,
                            padding: "9px 12px",
                            borderRadius: 10,
                            textDecoration: "none",
                            fontWeight: 900,
                          }}
                        >
                          {/* FIX: label correto baseado em link_tipo */}
                          {labelLink(r)}
                        </a>
                      </div>
                    );
                  })}
                </section>

                {ativo && (
                  <section
                    style={{
                      background: T.card,
                      border: `1px solid ${T.border}`,
                      borderRadius: 20,
                      padding: "clamp(14px, 4vw, 22px)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 12,
                        alignItems: "center",
                        flexWrap: "wrap",
                        marginBottom: 14,
                      }}
                    >
                      <div>
                        <LojaTag id={ativo.loja_id} nome={ativo.loja} />
                        <h2 style={{ margin: "10px 0 0", fontSize: 22 }}>
                          Histórico estimado
                        </h2>
                      </div>

                      <a
                        href={ativo.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          background: lojaConf.cor || T.cyan,
                          color: "#000",
                          padding: "10px 14px",
                          borderRadius: 10,
                          textDecoration: "none",
                          fontWeight: 950,
                        }}
                      >
                        {/* FIX: label correto no botão do histórico */}
                        {ativo.link_tipo === "busca" ? "Abrir busca →" : "Abrir produto →"}
                      </a>
                    </div>

                    <div style={{ height: 260 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={ativo.historico}>
                          <XAxis dataKey="data" tick={{ fontSize: 11, fill: T.dim }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 11, fill: T.dim }} axisLine={false} tickLine={false} width={70} />
                          <Tooltip content={<TooltipChart />} />
                          <ReferenceLine y={meta} stroke={T.green} strokeDasharray="4 4" />
                          <Line
                            type="monotone"
                            dataKey="preco"
                            stroke={lojaConf.cor || T.cyan}
                            strokeWidth={3}
                            dot={false}
                            activeDot={{ r: 5 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </section>
                )}
              </div>
            )}

            {aba === "cupons" && (
              <section
                style={{
                  background: T.card,
                  border: `1px solid ${T.border}`,
                  borderRadius: 18,
                  padding: 18,
                }}
              >
                <h2 style={{ marginTop: 0 }}>Cupons estimados</h2>
                <p style={{ color: T.muted, lineHeight: 1.6 }}>
                  Sem API oficial de cupons das lojas, o sistema não consegue garantir que um cupom esteja ativo.
                  Por isso, eles aparecem como estimativa e devem ser testados no checkout.{" "}
                  <b style={{ color: T.orange }}>
                    Os preços exibidos NÃO incluem nenhum desconto de cupom.
                  </b>
                </p>

                <div style={{ display: "grid", gap: 10 }}>
                  {resultados
                    .filter((r) => r.melhor_cupom)
                    .map((r) => (
                      <div
                        key={`cupom-${r.loja_id}`}
                        style={{
                          background: T.cardAlt,
                          border: `1px solid ${T.border}`,
                          borderRadius: 14,
                          padding: 14,
                        }}
                      >
                        <LojaTag id={r.loja_id} nome={r.loja} />
                        <div style={{ marginTop: 10 }}>
                          Cupom: <b style={{ color: T.orange }}>{r.melhor_cupom.codigo}</b>
                        </div>
                        {/* FIX: era "Preço estimado" sugerindo que o cupom foi aplicado.
                            Agora mostra o preço real sem qualquer cálculo de desconto. */}
                        <div>
                          Preço real:{" "}
                          <b>{formatarMoeda(r.precoFinal)}</b>
                          <span style={{ color: T.muted, fontSize: 12, marginLeft: 6 }}>
                            (cupom não aplicado)
                          </span>
                        </div>
                        <div style={{ color: T.muted, fontSize: 13 }}>
                          {r.melhor_cupom.condicao}
                        </div>
                        <a
                          href={r.url}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            display: "inline-block",
                            marginTop: 10,
                            color: T.cyan,
                            fontWeight: 900,
                            textDecoration: "none",
                          }}
                        >
                          Testar no site →
                        </a>
                      </div>
                    ))}
                </div>
              </section>
            )}

            <section
              style={{
                background: T.cyanDim,
                border: `1px solid ${T.cyan}30`,
                borderRadius: 18,
                padding: "18px 20px",
                marginTop: 16,
              }}
            >
              <div
                style={{
                  color: T.cyan,
                  fontSize: 12,
                  fontWeight: 950,
                  textTransform: "uppercase",
                  letterSpacing: 1,
                  marginBottom: 8,
                }}
              >
                🤖 Análise automática
              </div>

              <p style={{ margin: 0, color: T.text, lineHeight: 1.7 }}>
                {dados.analise}
              </p>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function Resumo({ label, value, color = T.text }) {
  return (
    <div
      style={{
        background: T.card,
        border: `1px solid ${T.border}`,
        borderRadius: 18,
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <span
        style={{
          color: T.muted,
          fontSize: 12,
          textTransform: "uppercase",
          letterSpacing: 1,
          fontWeight: 900,
        }}
      >
        {label}
      </span>
      <strong style={{ color, fontSize: 20 }}>{value}</strong>
    </div>
  );
}

export default function App() {
  const [tela, setTela] = useState("busca");
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");
  const [dados, setDados] = useState(null);
  const [meta, setMeta] = useState(0);

  async function handleBuscar(form) {
    setCarregando(true);
    setErro("");

    try {
      const response = await fetch(`${API_URL}/buscar`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          nome: form.nome,
          preco_meta: form.meta,
          email: form.email,
          alerta_proximo_pct: form.proximidade,
          aceita_usado: form.aceitaUsado,
          aceita_novo: form.aceitaNovo,
        }),
      });

      if (!response.ok) {
        throw new Error("Erro na API");
      }

      const data = await response.json();

      setDados(data);
      setMeta(form.meta);
      setTela("resultado");
    } catch (error) {
      console.error(error);
      setErro("Erro ao buscar produto. Confira se o backend Railway está online.");
    } finally {
      setCarregando(false);
    }
  }

  if (tela === "resultado" && dados) {
    return (
      <PainelResultado
        dados={dados}
        meta={meta}
        onNovaBusca={() => {
          setTela("busca");
          setDados(null);
        }}
      />
    );
  }

  return <TelaBusca onBuscar={handleBuscar} carregando={carregando} erro={erro} />;
}