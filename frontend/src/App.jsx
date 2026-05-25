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
  orangeDim: "#ffab4018",
  red: "#ff5252",
  purple: "#ce93d8",
  text: "#dde3f5",
  muted: "#8d9ac0",
  dim: "#4a5568",
};

const LOJAS = {
  mercadolivre: {
    nome: "Mercado Livre",
    cor: "#ffe600",
    bg: "#ffe60015",
    emoji: "🛒",
  },
  amazon: {
    nome: "Amazon",
    cor: "#ff9900",
    bg: "#ff990015",
    emoji: "📦",
  },
  kabum: {
    nome: "KaBuM!",
    cor: "#f04e23",
    bg: "#f04e2315",
    emoji: "🖥️",
  },
  magalu: {
    nome: "Magalu",
    cor: "#0086ff",
    bg: "#0086ff15",
    emoji: "🛍️",
  },
  olx: {
    nome: "OLX",
    cor: "#9adc00",
    bg: "#9adc0015",
    emoji: "🏷️",
  },
  enjoei: {
    nome: "Enjoei",
    cor: "#ff69b4",
    bg: "#ff69b415",
    emoji: "✨",
  },
};

const CUPONS_ESTIMADOS = {
  mercadolivre: [
    {
      codigo: "MELI5",
      desc_pct: 5,
      desc_fixo: 0,
      tipo: "percentual",
      condicao: "Estimado para compras selecionadas",
    },
    {
      codigo: "APPML10",
      desc_pct: 10,
      desc_fixo: 0,
      tipo: "percentual",
      condicao: "Estimado para compra pelo app",
    },
  ],
  amazon: [
    {
      codigo: "APP10",
      desc_pct: 10,
      desc_fixo: 0,
      tipo: "percentual",
      condicao: "Estimado para compra pelo app",
    },
    {
      codigo: "PRIME30",
      desc_pct: 0,
      desc_fixo: 30,
      tipo: "fixo",
      condicao: "Estimado para assinantes Prime",
    },
  ],
  kabum: [
    {
      codigo: "KABUM10",
      desc_pct: 10,
      desc_fixo: 0,
      tipo: "percentual",
      condicao: "Estimado para Pix/Boleto",
    },
    {
      codigo: "KABUM5",
      desc_pct: 5,
      desc_fixo: 0,
      tipo: "percentual",
      condicao: "Estimado para produtos selecionados",
    },
  ],
  magalu: [
    {
      codigo: "APP15",
      desc_pct: 15,
      desc_fixo: 0,
      tipo: "percentual",
      condicao: "Estimado para app Magalu",
    },
    {
      codigo: "PIX5",
      desc_pct: 5,
      desc_fixo: 0,
      tipo: "percentual",
      condicao: "Estimado para pagamento Pix",
    },
  ],
  olx: [
    {
      codigo: "OLXAPP",
      desc_pct: 5,
      desc_fixo: 0,
      tipo: "percentual",
      condicao: "Estimado para app OLX",
    },
  ],
  enjoei: [
    {
      codigo: "PRIMEIROENJOI",
      desc_pct: 10,
      desc_fixo: 0,
      tipo: "percentual",
      condicao: "Estimado para primeira compra",
    },
  ],
};

function formatarMoeda(valor) {
  return Number(valor || 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function encodeBusca(texto) {
  return encodeURIComponent(texto || "").replaceAll("%20", "+");
}

function calcPrecoFinal(preco, cupom) {
  if (!cupom) return preco;

  if (cupom.tipo === "percentual") {
    return Number((preco * (1 - cupom.desc_pct / 100)).toFixed(2));
  }

  if (cupom.tipo === "fixo") {
    return Number(Math.max(0, preco - cupom.desc_fixo).toFixed(2));
  }

  return preco;
}

function melhorCupom(lojaId, preco) {
  const cupons = CUPONS_ESTIMADOS[lojaId] || [];
  let melhor = null;
  let menor = preco;

  for (const cupom of cupons) {
    const final = calcPrecoFinal(preco, cupom);

    if (final < menor) {
      menor = final;
      melhor = cupom;
    }
  }

  return melhor;
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

function gerarResultadosLocais(nome, meta, aceitaNovo, aceitaUsado) {
  const seed = nome
    .toLowerCase()
    .split("")
    .reduce((acc, char) => acc + char.charCodeAt(0), 0);

  const base = Math.max(300, Number(meta || 1000) * (1.05 + (seed % 35) / 100));

  const config = [
    {
      loja_id: "mercadolivre",
      fator: 1,
      condicao: "Novo",
      url: `https://lista.mercadolivre.com.br/${encodeBusca(nome)}`,
      link_tipo: "busca",
    },
    {
      loja_id: "amazon",
      fator: 0.96,
      condicao: "Novo",
      url: `https://www.amazon.com.br/s?k=${encodeBusca(nome)}`,
      link_tipo: "busca",
    },
    {
      loja_id: "kabum",
      fator: 0.92,
      condicao: "Novo",
      url: `https://www.kabum.com.br/busca/${encodeBusca(nome)}`,
      link_tipo: "busca",
    },
    {
      loja_id: "magalu",
      fator: 0.98,
      condicao: "Novo",
      url: `https://www.magazineluiza.com.br/busca/${encodeBusca(nome)}/`,
      link_tipo: "busca",
    },
    {
      loja_id: "olx",
      fator: 0.78,
      condicao: "Usado",
      url: `https://www.olx.com.br/brasil?q=${encodeBusca(nome)}`,
      link_tipo: "busca",
    },
    {
      loja_id: "enjoei",
      fator: 0.82,
      condicao: "Seminovo",
      url: `https://www.enjoei.com.br/busca?q=${encodeBusca(nome)}`,
      link_tipo: "busca",
    },
  ];

  return config
    .filter((item) => {
      const ehUsado =
        item.condicao.toLowerCase().includes("usado") ||
        item.condicao.toLowerCase().includes("seminovo");

      if (ehUsado && !aceitaUsado) return false;
      if (!ehUsado && !aceitaNovo) return false;

      return true;
    })
    .map((item) => {
      const loja = LOJAS[item.loja_id];
      const variacao = 1 + (Math.random() * 0.08 - 0.04);
      const preco = Number((base * item.fator * variacao).toFixed(2));
      const cupom = melhorCupom(item.loja_id, preco);
      const precoFinal = cupom ? calcPrecoFinal(preco, cupom) : preco;

      return {
        loja_id: item.loja_id,
        loja: loja.nome,
        preco,
        preco_final: precoFinal,
        titulo: `${nome} - ${loja.nome}`,
        condicao: item.condicao,
        url: item.url,
        melhor_cupom: cupom,
        cupom_confirmado: false,
        observacao_cupom: cupom
          ? "Cupom estimado. Confirme a validade no checkout da loja."
          : "",
        link_tipo: item.link_tipo,
      };
    })
    .sort((a, b) => a.preco_final - b.preco_final);
}

function normalizarResultadosBackend(resultados) {
  return (resultados || [])
    .map((r) => {
      const preco = Number(r.preco || 0);
      const precoFinal = Number(r.preco_final || r.preco || 0);
      const cupom = r.melhor_cupom || null;

      const url = r.url || "";
      const linkTipo =
        url &&
        !url.includes("/busca") &&
        !url.includes("search") &&
        !url.includes("?q=") &&
        !url.includes("/s?k=")
          ? "produto"
          : "busca";

      return {
        loja_id: r.loja_id,
        loja: r.loja || LOJAS[r.loja_id]?.nome || r.loja_id || "Loja",
        preco,
        preco_final: precoFinal,
        titulo: r.titulo || "Produto encontrado",
        condicao: r.condicao || "Não informado",
        url,
        melhor_cupom: cupom,
        cupom_confirmado: Boolean(r.cupom_confirmado),
        observacao_cupom:
          r.observacao_cupom ||
          (cupom ? "Cupom estimado. Confirme no checkout da loja." : ""),
        link_tipo: linkTipo,
      };
    })
    .filter((r) => r.preco_final > 0)
    .sort((a, b) => a.preco_final - b.preco_final);
}

function Chip({ children, color = T.cyan, bg, style = {} }) {
  return (
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
}

function LojaTag({ id, nome }) {
  const loja = LOJAS[id] || {
    nome: nome || "Loja",
    cor: T.cyan,
    bg: T.cyanDim,
    emoji: "🏬",
  };

  return (
    <Chip color={loja.cor} bg={loja.bg}>
      {loja.emoji} {loja.nome}
    </Chip>
  );
}

function TooltipChart({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="tooltip-chart">
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
    <main className="app-bg page-center">
      <section className="search-shell">
        <div className="hero">
          <div className="hero-badge">🎯 Monitor inteligente</div>

          <h1>
            Monitor de <span>Preços</span>
          </h1>

          <p>
            Monitore produtos novos e usados, receba alerta por email e compare lojas.
          </p>
        </div>

        <div className="search-card">
          <div className="form-grid">
            <div className="form-field full">
              <label htmlFor="produto">Produto</label>
              <input
                id="produto"
                ref={inputRef}
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && enviarBusca()}
                placeholder="Ex: Ryzen 7 5700X, iPhone 15, RTX 4070..."
              />
            </div>

            <div className="form-field">
              <label htmlFor="preco-meta">Preço meta</label>
              <input
                id="preco-meta"
                value={meta}
                onChange={(e) => setMeta(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && enviarBusca()}
                placeholder="Ex: 950"
                type="number"
              />
            </div>

            <div className="form-field">
              <label htmlFor="proximidade">Proximidade</label>
              <input
                id="proximidade"
                value={proximidade}
                onChange={(e) => setProximidade(e.target.value)}
                type="number"
                min="1"
                max="100"
              />
            </div>

            <div className="form-field full">
              <label htmlFor="email-alerta">Email para alerta</label>
              <input
                id="email-alerta"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="seuemail@gmail.com"
                type="email"
              />
            </div>
          </div>

          <div className="check-row">
            <label className="check-label">
              <input
                type="checkbox"
                checked={aceitaNovo}
                onChange={(e) => setAceitaNovo(e.target.checked)}
              />
              Aceitar novo
            </label>

            <label className="check-label">
              <input
                type="checkbox"
                checked={aceitaUsado}
                onChange={(e) => setAceitaUsado(e.target.checked)}
              />
              Aceitar usado/seminovo
            </label>
          </div>

          <button className="primary-button" disabled={!podeBuscar} onClick={enviarBusca}>
            {carregando ? "🔍 Buscando nas lojas..." : "🔍 Buscar e monitorar"}
          </button>

          {erro && <div className="erro">{erro}</div>}

          <p className="hint">
            Cupons aparecem como estimativa. Confirme a validade no checkout da loja.
          </p>
        </div>
      </section>
    </main>
  );
}

function Resumo({ label, value, color = T.text }) {
  return (
    <div className="summary-card">
      <span>{label}</span>
      <strong style={{ color }}>{value}</strong>
    </div>
  );
}

function PainelResultado({ dados, meta, onNovaBusca }) {
  const [lojaAtiva, setLojaAtiva] = useState(null);
  const [aba, setAba] = useState("precos");

  const resultados = useMemo(() => {
    return normalizarResultadosBackend(dados.resultados)
      .map((r) => ({
        ...r,
        historico: gerarHistorico(r.preco_final),
      }))
      .sort((a, b) => a.preco_final - b.preco_final);
  }, [dados]);

  useEffect(() => {
    if (!lojaAtiva && resultados[0]) {
      setLojaAtiva(resultados[0].loja_id);
    }
  }, [resultados, lojaAtiva]);

  const ativo = resultados.find((r) => r.loja_id === lojaAtiva) || resultados[0];
  const lojaConf = LOJAS[ativo?.loja_id] || { cor: T.cyan };
  const melhor = resultados[0];

  return (
    <main className="dashboard-page">
      <div className="dashboard-container">
        <header className="dashboard-header">
          <div>
            <div className="eyebrow">🎯 Monitorando</div>
            <h1>{dados.produto_normalizado}</h1>
            <p>
              Meta: <b>{formatarMoeda(meta)}</b>
              {dados.email && (
                <>
                  {" "}
                  · alerta em <b>{dados.email}</b>
                </>
              )}
            </p>

            {dados.modo_local && (
              <div className="warning">
                ⚠️ O backend não retornou resultados reais. Exibindo simulação local
                para manter o painel ativo.
              </div>
            )}
          </div>

          <button className="new-search" onClick={onNovaBusca}>
            + Nova busca
          </button>
        </header>

        {resultados.length === 0 ? (
          <section className="empty-card">
            <h2>Nenhum preço encontrado agora</h2>
            <p>{dados.analise}</p>
            <button className="new-search" onClick={onNovaBusca}>
              Fazer nova busca
            </button>
          </section>
        ) : (
          <>
            <section className="summary-grid">
              <Resumo
                label="Melhor preço"
                value={formatarMoeda(melhor?.preco_final)}
                color={T.green}
              />
              <Resumo label="Loja destaque" value={melhor?.loja || "-"} />
              <Resumo label="Condição" value={melhor?.condicao || "-"} />
              <Resumo
                label="Status"
                value={melhor?.preco_final <= meta ? "Dentro da meta" : "Monitorando"}
                color={melhor?.preco_final <= meta ? T.green : T.orange}
              />
            </section>

            <div className="tabs">
              <button
                className={aba === "precos" ? "active" : ""}
                onClick={() => setAba("precos")}
              >
                💰 Preços
              </button>
              <button
                className={aba === "cupons" ? "active" : ""}
                onClick={() => setAba("cupons")}
              >
                🎟️ Cupons estimados
              </button>
            </div>

            {aba === "precos" && (
              <div className="result-layout">
                <section className="cards-grid">
                  {resultados.map((r, index) => {
                    const loja = LOJAS[r.loja_id] || {
                      cor: T.cyan,
                      bg: T.cyanDim,
                    };

                    const atingiu = r.preco_final <= meta;
                    const selecionada = lojaAtiva === r.loja_id;

                    return (
                      <article
                        key={`${r.loja_id}-${index}`}
                        className={`price-card ${selecionada ? "selected" : ""}`}
                        onClick={() => setLojaAtiva(r.loja_id)}
                        style={{
                          borderColor: selecionada ? `${loja.cor}80` : T.border,
                          boxShadow: selecionada ? `0 0 24px ${loja.cor}16` : "none",
                        }}
                      >
                        <div className="card-chips">
                          <LojaTag id={r.loja_id} nome={r.loja} />
                          {index === 0 && <Chip color={T.green}>🏆 Melhor</Chip>}
                          {atingiu && <Chip color={T.green}>✅ Meta</Chip>}
                          {r.link_tipo === "produto" ? (
                            <Chip color={T.green}>🔗 Produto</Chip>
                          ) : (
                            <Chip color={T.orange}>🔎 Busca</Chip>
                          )}
                        </div>

                        <div className="price-value">{formatarMoeda(r.preco_final)}</div>

                        {r.preco_final !== Number(r.preco) && (
                          <div className="base-price">
                            Preço base: {formatarMoeda(r.preco)}
                          </div>
                        )}

                        <div className="product-title">
                          {r.condicao} · {r.titulo || "Produto encontrado"}
                        </div>

                        {r.melhor_cupom && (
                          <div className="coupon-line">
                            🎟️ Cupom estimado: <b>{r.melhor_cupom.codigo}</b>
                          </div>
                        )}

                        {r.observacao_cupom && (
                          <div className="coupon-warning">{r.observacao_cupom}</div>
                        )}

                        {r.url ? (
                          <a
                            href={r.url}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="open-link"
                            style={{ background: loja.cor || T.cyan }}
                          >
                            {r.link_tipo === "produto" ? "Ver produto →" : "Ver busca →"}
                          </a>
                        ) : (
                          <div className="no-link">Link não encontrado</div>
                        )}
                      </article>
                    );
                  })}
                </section>

                {ativo && (
                  <section className="chart-card">
                    <div className="chart-header">
                      <div>
                        <LojaTag id={ativo.loja_id} nome={ativo.loja} />
                        <h2>Histórico estimado</h2>
                      </div>

                      {ativo.url && (
                        <a
                          href={ativo.url}
                          target="_blank"
                          rel="noreferrer"
                          className="chart-link"
                          style={{ background: lojaConf.cor || T.cyan }}
                        >
                          {ativo.link_tipo === "produto"
                            ? "Abrir produto →"
                            : "Abrir busca →"}
                        </a>
                      )}
                    </div>

                    <div className="chart-wrap">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={ativo.historico}>
                          <XAxis
                            dataKey="data"
                            tick={{ fontSize: 11, fill: T.dim }}
                            axisLine={false}
                            tickLine={false}
                          />
                          <YAxis
                            tick={{ fontSize: 11, fill: T.dim }}
                            axisLine={false}
                            tickLine={false}
                            width={70}
                          />
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
              <section className="coupon-panel">
                <h2>Cupons estimados</h2>
                <p>
                  Sem API oficial de cupons das lojas, o sistema não consegue garantir que
                  um cupom esteja ativo. Por isso, eles aparecem como estimativa e devem ser
                  testados no checkout.
                </p>

                <div className="coupon-grid">
                  {resultados.filter((r) => r.melhor_cupom).length === 0 && (
                    <div className="no-coupon">
                      Nenhum cupom estimado para os resultados atuais.
                    </div>
                  )}

                  {resultados
                    .filter((r) => r.melhor_cupom)
                    .map((r, index) => (
                      <article className="coupon-card" key={`cupom-${r.loja_id}-${index}`}>
                        <LojaTag id={r.loja_id} nome={r.loja} />

                        <div className="coupon-code">
                          Cupom: <b>{r.melhor_cupom.codigo}</b>
                        </div>

                        <div>
                          Preço estimado: <b>{formatarMoeda(r.preco_final)}</b>
                        </div>

                        <p>{r.melhor_cupom.condicao}</p>

                        {r.url && (
                          <a href={r.url} target="_blank" rel="noreferrer">
                            Testar no site →
                          </a>
                        )}
                      </article>
                    ))}
                </div>
              </section>
            )}

            <section className="analysis-card">
              <div>🤖 Análise automática</div>
              <p>{dados.analise}</p>
            </section>
          </>
        )}
      </div>

    </main>
  );
}


function GlobalStyles() {
  return (
    <style>{`
      * {
        box-sizing: border-box;
      }

      html,
      body,
      #root {
        margin: 0;
        width: 100%;
        min-height: 100%;
        background: #070a12;
      }

      body {
        overflow-x: hidden;
        font-family: Inter, Segoe UI, Arial, sans-serif;
        color: #f8fafc;
      }

      button,
      input {
        font-family: inherit;
      }

      .app-bg,
      .page-center,
      .dashboard-page {
        min-height: 100vh;
        background:
          radial-gradient(circle at 18% 20%, rgba(124, 92, 255, 0.24), transparent 28%),
          radial-gradient(circle at 78% 18%, rgba(34, 211, 238, 0.12), transparent 26%),
          radial-gradient(circle at 55% 100%, rgba(34, 197, 94, 0.07), transparent 28%),
          #070a12;
        color: #f8fafc;
      }

      .page-center {
        width: 100%;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: clamp(20px, 4vw, 44px);
      }

      .search-shell {
        width: min(100%, 1120px);
        display: grid;
        grid-template-columns: minmax(320px, 0.95fr) minmax(420px, 1fr);
        gap: clamp(36px, 6vw, 86px);
        align-items: center;
      }

      .hero {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
      }

      .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        width: fit-content;
        background: rgba(124, 92, 255, 0.14);
        border: 1px solid rgba(124, 92, 255, 0.35);
        color: #c4b5fd;
        border-radius: 999px;
        padding: 8px 12px;
        font-size: 12px;
        font-weight: 900;
        letter-spacing: 0.4px;
        text-transform: uppercase;
        margin-bottom: 20px;
      }

      .hero-icon {
        display: none;
      }

      .hero h1 {
        margin: 0;
        max-width: 520px;
        font-size: clamp(54px, 5.7vw, 82px);
        line-height: 0.92;
        letter-spacing: -4px;
        font-weight: 950;
        color: #f8fafc;
      }

      .hero h1 span {
        display: block;
        background: linear-gradient(135deg, #7c5cff 0%, #22d3ee 100%);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
      }

      .hero p {
        max-width: 480px;
        margin: 24px 0 0;
        color: #a7b6d5;
        font-size: 18px;
        line-height: 1.65;
      }

      .search-card {
        width: 100%;
        max-width: 610px;
        justify-self: end;
        background: rgba(17, 24, 39, 0.92);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 30px;
        padding: 34px 36px;
        box-shadow:
          0 28px 90px rgba(0, 0, 0, 0.48),
          inset 0 1px 0 rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(16px);
      }

      .form-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        column-gap: 18px;
        row-gap: 18px;
      }

      .form-field {
        display: flex;
        flex-direction: column;
        gap: 9px;
        min-width: 0;
      }

      .form-field.full {
        grid-column: 1 / -1;
      }

      .search-card label {
        display: block;
        margin: 0 !important;
        padding: 0 !important;
        position: static !important;
        transform: none !important;
        color: #a9b7d4;
        font-size: 11px;
        font-weight: 950;
        text-transform: uppercase;
        letter-spacing: 1px;
        line-height: 1.2;
      }

      .search-card input {
        display: block;
        margin: 0 !important;
        width: 100%;
        height: 58px;
        border-radius: 16px;
        padding: 0 18px;
        font-size: 16px;
        background: #070c16;
        border: 1.5px solid #31415f;
        color: #f8fafc;
        outline: none;
        transition: 0.18s ease;
      }

      .search-card input::placeholder {
        color: #64748b;
      }

      .search-card input:focus {
        border-color: #7c5cff;
        box-shadow: 0 0 0 4px rgba(124, 92, 255, 0.18);
      }

      .check-row {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin: 22px 0 20px;
      }

      .check-label {
        display: inline-flex !important;
        align-items: center;
        gap: 8px;
        height: 42px;
        margin: 0 !important;
        padding: 0 16px;
        border-radius: 999px;
        background: rgba(32, 44, 68, 0.9);
        border: 1px solid #354869;
        color: #f8fafc !important;
        font-size: 15px !important;
        font-weight: 800 !important;
        text-transform: none !important;
        letter-spacing: 0 !important;
        cursor: pointer;
      }

      .check-label input {
        width: 15px;
        height: 15px;
        accent-color: #7c5cff;
      }

      .primary-button,
      .search-card button {
        width: 100%;
        height: 60px;
        margin-top: 2px;
        background: linear-gradient(135deg, #7c5cff, #4f8cff);
        border: 0;
        border-radius: 17px;
        color: white;
        font-size: 16px;
        font-weight: 950;
        cursor: pointer;
        box-shadow: 0 14px 34px rgba(124, 92, 255, 0.28);
        transition: 0.18s ease;
      }

      .primary-button:hover:not(:disabled),
      .search-card button:hover:not(:disabled) {
        transform: translateY(-1px);
        filter: brightness(1.08);
      }

      .primary-button:disabled,
      .search-card button:disabled {
        background: linear-gradient(135deg, #344766, #2b3b57);
        color: #a8b3c7;
        opacity: 0.75;
        cursor: not-allowed;
        box-shadow: none;
      }

      .hint {
        margin: 18px 0 0;
        color: #a8b3c7;
        font-size: 13px;
        line-height: 1.55;
        text-align: center;
      }

      .erro {
        margin-top: 14px;
        color: #fb7185;
        font-size: 13px;
        text-align: center;
        font-weight: 700;
      }

      .dashboard-page {
        width: 100vw;
        padding: clamp(14px, 2vw, 28px);
        font-family: Inter, Segoe UI, Arial, sans-serif;
      }

      .dashboard-container {
        width: 100%;
        max-width: none;
        margin: 0;
      }

      .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        margin-bottom: 18px;
        flex-wrap: wrap;
      }

      .eyebrow {
        font-size: 11px;
        color: #c4b5fd;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 900;
      }

      .dashboard-header h1 {
        margin: 4px 0;
        font-size: clamp(28px, 5vw, 46px);
        letter-spacing: -1.5px;
        line-height: 1.05;
      }

      .dashboard-header p {
        color: #94a3b8;
        font-size: 14px;
        margin: 0;
        line-height: 1.6;
      }

      .dashboard-header b {
        color: #22d3ee;
      }

      .warning {
        color: #fbbf24;
        font-size: 13px;
        margin-top: 8px;
        line-height: 1.5;
        max-width: 760px;
      }

      .new-search {
        background: rgba(28, 38, 59, 0.8);
        color: #f8fafc;
        border: 1px solid #334466;
        border-radius: 13px;
        padding: 11px 15px;
        font-weight: 900;
        cursor: pointer;
        white-space: nowrap;
      }

      .empty-card,
      .summary-card,
      .price-card,
      .chart-card,
      .coupon-panel,
      .analysis-card {
        background: rgba(17, 24, 39, 0.88);
        border: 1px solid rgba(148, 163, 184, 0.16);
        box-shadow: 0 18px 54px rgba(0, 0, 0, 0.22);
      }

      .empty-card {
        border-radius: 22px;
        padding: clamp(18px, 4vw, 28px);
        text-align: center;
      }

      .empty-card p {
        color: #94a3b8;
        line-height: 1.6;
      }

      .summary-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 16px;
      }

      .summary-card {
        border-radius: 20px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-width: 0;
      }

      .summary-card span {
        color: #94a3b8;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 900;
      }

      .summary-card strong {
        font-size: clamp(18px, 3vw, 24px);
        word-break: break-word;
      }

      .tabs {
        display: flex;
        gap: 6px;
        background: rgba(17, 24, 39, 0.76);
        border: 1px solid #27344f;
        border-radius: 16px;
        padding: 5px;
        margin-bottom: 16px;
      }

      .tabs button {
        flex: 1;
        padding: 12px 8px;
        border-radius: 12px;
        border: none;
        background: transparent;
        color: #94a3b8;
        font-weight: 900;
        cursor: pointer;
      }

      .tabs button.active {
        background: linear-gradient(135deg, rgba(124, 92, 255, 0.26), rgba(34, 211, 238, 0.14));
        color: #f8fafc;
      }

      .result-layout {
        display: grid;
        grid-template-columns: minmax(0, 1.45fr) minmax(420px, 0.55fr);
        gap: 16px;
        align-items: start;
        width: 100%;
      }

      .cards-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(280px, 1fr));
        gap: 14px;
        width: 100%;
      }

      .price-card {
        border-radius: 20px;
        padding: 16px;
        color: #f8fafc;
        cursor: pointer;
        min-width: 0;
        transition: transform 0.15s ease, border-color 0.15s ease;
      }

      .price-card:hover {
        transform: translateY(-2px);
      }

      .price-card.selected {
        background: rgba(28, 38, 59, 0.92);
      }

      .card-chips {
        display: flex;
        gap: 7px;
        flex-wrap: wrap;
        margin-bottom: 10px;
      }

      .price-value {
        color: #22c55e;
        font-size: clamp(24px, 5vw, 34px);
        font-weight: 950;
        margin-bottom: 6px;
      }

      .base-price,
      .product-title,
      .coupon-warning {
        color: #94a3b8;
        font-size: 13px;
        line-height: 1.5;
      }

      .coupon-line {
        color: #fbbf24;
        font-size: 13px;
        margin-top: 8px;
      }

      .open-link,
      .chart-link {
        display: inline-block;
        margin-top: 12px;
        color: #08111f;
        padding: 9px 12px;
        border-radius: 10px;
        text-decoration: none;
        font-weight: 950;
      }

      .no-link {
        color: #94a3b8;
        margin-top: 12px;
        font-size: 13px;
      }

      .chart-card {
        border-radius: 22px;
        padding: clamp(16px, 3vw, 22px);
        min-width: 0;
        position: sticky;
        top: 18px;
      }

      .chart-header {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        flex-wrap: wrap;
        margin-bottom: 14px;
      }

      .chart-header h2 {
        margin: 10px 0 0;
        font-size: clamp(18px, 4vw, 24px);
      }

      .chart-wrap {
        height: clamp(240px, 32vw, 330px);
        width: 100%;
      }

      .tooltip-chart {
        background: #111827;
        border: 1px solid #27344f;
        border-radius: 10px;
        padding: 9px 12px;
        font-size: 12px;
      }

      .coupon-panel {
        border-radius: 22px;
        padding: clamp(16px, 4vw, 22px);
      }

      .coupon-panel h2 {
        margin-top: 0;
      }

      .coupon-panel p {
        color: #94a3b8;
        line-height: 1.6;
      }

      .coupon-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 12px;
      }

      .coupon-card {
        background: rgba(28, 38, 59, 0.78);
        border: 1px solid #27344f;
        border-radius: 16px;
        padding: 15px;
      }

      .coupon-code {
        margin-top: 10px;
      }

      .coupon-code b {
        color: #fbbf24;
      }

      .coupon-card p {
        color: #94a3b8;
        font-size: 13px;
      }

      .coupon-card a {
        display: inline-block;
        margin-top: 10px;
        color: #22d3ee;
        font-weight: 900;
        text-decoration: none;
      }

      .analysis-card {
        border-radius: 20px;
        padding: 18px 20px;
        margin-top: 16px;
        background: linear-gradient(135deg, rgba(124, 92, 255, 0.18), rgba(34, 211, 238, 0.08));
      }

      .analysis-card div {
        color: #c4b5fd;
        font-size: 12px;
        font-weight: 950;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
      }

      .analysis-card p {
        margin: 0;
        color: #f8fafc;
        line-height: 1.7;
      }

      @media (min-width: 1700px) {
        .cards-grid {
          grid-template-columns: repeat(4, minmax(280px, 1fr));
        }
      }

      @media (max-width: 1150px) {
        .search-shell {
          grid-template-columns: 1fr;
          max-width: 620px;
          gap: 34px;
        }

        .hero {
          align-items: center;
          text-align: center;
        }

        .hero h1 {
          max-width: 620px;
          font-size: clamp(44px, 9vw, 68px);
          letter-spacing: -3px;
        }

        .hero p {
          max-width: 560px;
        }

        .search-card {
          justify-self: center;
        }

        .result-layout {
          grid-template-columns: 1fr;
        }

        .chart-card {
          position: static;
        }

        .cards-grid {
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        }

        .summary-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }

      @media (max-width: 680px) {
        .page-center {
          padding: 18px;
          align-items: flex-start;
        }

        .search-shell {
          gap: 24px;
          padding-top: 24px;
        }

        .hero h1 {
          font-size: clamp(40px, 13vw, 56px);
          letter-spacing: -2.5px;
        }

        .hero p {
          font-size: 15px;
        }

        .search-card {
          padding: 24px;
          border-radius: 22px;
        }

        .form-grid {
          grid-template-columns: 1fr;
          row-gap: 18px;
        }

        .search-card input {
          height: 54px;
        }

        .check-row {
          flex-direction: column;
        }

        .check-label {
          width: 100%;
          justify-content: center;
        }

        .dashboard-header {
          flex-direction: column;
          align-items: stretch;
        }

        .new-search {
          width: 100%;
        }

        .tabs {
          flex-direction: column;
        }

        .cards-grid,
        .summary-grid,
        .coupon-grid {
          grid-template-columns: 1fr;
        }

        .chart-header {
          align-items: stretch;
        }

        .chart-link {
          width: 100%;
          text-align: center;
        }
      }
    `}</style>
  );
}

export default function App() {
  const [tela, setTela] = useState("busca");
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");
  const [dados, setDados] = useState(null);
  const [meta, setMeta] = useState(0);

  async function buscarNoBackend(form) {
    const controller = new AbortController();

    const timer = setTimeout(() => {
      controller.abort();
    }, 15000);

    try {
      const response = await fetch(`${API_URL}/buscar`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({
          nome: form.nome,
          preco_meta: form.meta,
          email: form.email,
          alerta_proximo_pct: form.proximidade,
          aceita_usado: form.aceitaUsado,
          aceita_novo: form.aceitaNovo,
          cupom: "",
          desconto_pct: 0,
        }),
      });

      clearTimeout(timer);

      if (!response.ok) {
        throw new Error(`Erro HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timer);
      throw error;
    }
  }

  async function handleBuscar(form) {
    setCarregando(true);
    setErro("");

    try {
      const data = await buscarNoBackend(form);
      const resultadosBackend = normalizarResultadosBackend(data.resultados);

      if (resultadosBackend.length === 0) {
        const resultadosLocais = gerarResultadosLocais(
          form.nome,
          form.meta,
          form.aceitaNovo,
          form.aceitaUsado
        );

        setDados({
          ...data,
          produto_normalizado: data.produto_normalizado || form.nome,
          meta: form.meta,
          email: form.email,
          resultados: resultadosLocais,
          modo_local: true,
          analise:
            "O backend respondeu, mas não encontrou resultados reais agora. O painel foi carregado com simulação local para visualização. O produto foi salvo e continuará sendo monitorado.",
        });
      } else {
        setDados({
          ...data,
          resultados: resultadosBackend,
          modo_local: false,
        });
      }

      setMeta(form.meta);
      setTela("resultado");
    } catch (error) {
      console.error("Backend falhou. Usando fallback local:", error);

      const resultadosLocais = gerarResultadosLocais(
        form.nome,
        form.meta,
        form.aceitaNovo,
        form.aceitaUsado
      );

      setDados({
        id: null,
        produto_normalizado: form.nome,
        meta: form.meta,
        email: form.email,
        resultados: resultadosLocais,
        modo_local: true,
        analise:
          "O backend Railway não respondeu agora, então o painel foi carregado em modo de simulação local. Para alertas por email e links reais de produto, mantenha o backend publicado com a rota /buscar.",
      });

      setMeta(form.meta);
      setTela("resultado");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <>
      <GlobalStyles />

      {tela === "resultado" && dados ? (
        <PainelResultado
          dados={dados}
          meta={meta}
          onNovaBusca={() => {
            setTela("busca");
            setDados(null);
          }}
        />
      ) : (
        <TelaBusca onBuscar={handleBuscar} carregando={carregando} erro={erro} />
      )}
    </>
  );
}