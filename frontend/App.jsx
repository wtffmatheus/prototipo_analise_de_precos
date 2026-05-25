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
  orange: "#ffab40",
  red: "#ff5252",
  text: "#dde3f5",
  muted: "#7b88a8",
  dim: "#4a5568",
};

const lojaInfo = {
  mercadolivre: { nome: "Mercado Livre", cor: "#ffe600", bg: "#ffe60015", emoji: "🛒" },
  amazon: { nome: "Amazon", cor: "#ff9900", bg: "#ff990015", emoji: "📦" },
  kabum: { nome: "KaBuM!", cor: "#f04e23", bg: "#f04e2315", emoji: "🖥️" },
  magalu: { nome: "Magalu", cor: "#0086ff", bg: "#0086ff15", emoji: "🛍️" },
  olx: { nome: "OLX", cor: "#9adc00", bg: "#9adc0015", emoji: "🏷️" },
  enjoei: { nome: "Enjoei", cor: "#ff69b4", bg: "#ff69b415", emoji: "✨" },
};

function formatarMoeda(valor) {
  return Number(valor || 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function detectarTipoLink(url = "") {
  const u = String(url).toLowerCase();

  if (!u) return "sem_link";

  const pareceBusca =
    u.includes("/busca") ||
    u.includes("search") ||
    u.includes("?q=") ||
    u.includes("/s?k=") ||
    u.includes("lista.mercadolivre") ||
    u.includes("olx.com.br/brasil") ||
    u.includes("enjoei.com.br/busca");

  return pareceBusca ? "busca" : "produto";
}

function normalizarCupom(cupom, precoReal) {
  if (!cupom) return null;

  return {
    codigo: cupom.codigo || cupom.code || "CUPOM",
    condicao: cupom.condicao || cupom.descricao || "Possível cupom. Teste no checkout.",
    origem: cupom.origem || "Não informado",
    confianca: cupom.confianca || "baixa",
    verificado: Boolean(cupom.verificado || cupom.confirmado),
    preco_final_estimado: Number(cupom.preco_final_estimado || precoReal),
    aviso:
      cupom.aviso ||
      "Cupom possível, não confirmado. Não foi aplicado ao preço exibido.",
  };
}

function normalizarHistorico(historico) {
  if (!Array.isArray(historico)) return [];

  return historico
    .map((h) => ({
      data: h.data || h.criado_em || h.created_at || "",
      preco: Number(h.preco || h.preco_final || h.valor || 0),
    }))
    .filter((h) => h.preco > 0);
}

function normalizarResultadosBackend(resultados) {
  return (resultados || [])
    .map((r) => {
      // REGRA PRINCIPAL:
      // O preço exibido é o preço REAL vindo do backend.
      // Não usamos cupom para alterar preço no frontend.
      const precoReal = Number(r.preco ?? r.preco_real ?? r.valor ?? r.preco_final ?? 0);

      const possiveisCuponsRaw =
        r.possiveis_cupons ||
        r.cupons_possiveis ||
        r.cupons ||
        [];

      const possiveisCupons = Array.isArray(possiveisCuponsRaw)
        ? possiveisCuponsRaw
            .map((c) => normalizarCupom(c, precoReal))
            .filter(Boolean)
        : [];

      const melhorCupom = r.melhor_cupom
        ? normalizarCupom(r.melhor_cupom, precoReal)
        : possiveisCupons[0] || null;

      const url = r.url || "";
      const linkTipo = r.link_tipo || detectarTipoLink(url);

      return {
        loja_id: r.loja_id || r.id_loja || "loja",
        loja: r.loja || lojaInfo[r.loja_id]?.nome || r.loja_id || "Loja",
        precoReal,
        titulo: r.titulo || r.nome || "Produto encontrado",
        condicao: r.condicao || "Não informado",
        url,
        link_tipo: linkTipo,
        melhor_cupom: melhorCupom,
        possiveis_cupons: possiveisCupons,
        cupom_confirmado: Boolean(r.cupom_confirmado),
        historico: normalizarHistorico(r.historico || r.historico_real),
      };
    })
    .filter((r) => r.precoReal > 0)
    .sort((a, b) => a.precoReal - b.precoReal);
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
  const loja = lojaInfo[id] || {
    nome: nome || id || "Loja",
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
    <main className="page-center">
      <section className="search-shell">
        <div className="hero">
          <div className="hero-icon">🎯</div>
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
              <label>Produto</label>
              <input
                ref={inputRef}
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && enviarBusca()}
                placeholder="Ex: Ryzen 7 5700X, iPhone 15, RTX 4070..."
              />
            </div>

            <div className="form-field">
              <label>Preço meta</label>
              <input
                value={meta}
                onChange={(e) => setMeta(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && enviarBusca()}
                placeholder="Ex: 950"
                type="number"
              />
            </div>

            <div className="form-field">
              <label>Proximidade</label>
              <input
                value={proximidade}
                onChange={(e) => setProximidade(e.target.value)}
                type="number"
                min="1"
                max="100"
              />
            </div>

            <div className="form-field full">
              <label>Email para alerta</label>
              <input
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
            O sistema não inventa preço. Se nenhuma loja retornar produto real, você verá
            a mensagem de nenhum resultado encontrado.
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
    return normalizarResultadosBackend(dados.resultados);
  }, [dados]);

  useEffect(() => {
    if (!lojaAtiva && resultados[0]) {
      setLojaAtiva(resultados[0].loja_id);
    }
  }, [resultados, lojaAtiva]);

  const ativo = resultados.find((r) => r.loja_id === lojaAtiva) || resultados[0];
  const lojaConf = lojaInfo[ativo?.loja_id] || { cor: T.cyan };
  const melhor = resultados[0];

  const cupons = resultados.flatMap((r) =>
    (r.possiveis_cupons || []).map((cupom) => ({
      ...cupom,
      loja_id: r.loja_id,
      loja: r.loja,
      url: r.url,
      precoReal: r.precoReal,
    }))
  );

  return (
    <main className="dashboard-page">
      <div className="dashboard-container">
        <header className="dashboard-header">
          <div>
            <div className="eyebrow">🎯 Monitorando</div>
            <h1>{dados.produto_normalizado || dados.nome || "Produto"}</h1>
            <p>
              Meta: <b>{formatarMoeda(meta)}</b>
              {dados.email && (
                <>
                  {" "}
                  · alerta em <b>{dados.email}</b>
                </>
              )}
            </p>
          </div>

          <button className="new-search" onClick={onNovaBusca}>
            + Nova busca
          </button>
        </header>

        {resultados.length === 0 ? (
          <section className="empty-card">
            <h2>Nenhum preço real encontrado agora</h2>
            <p>
              O backend não retornou produtos reais para essa busca. Nenhum preço foi
              inventado pelo frontend.
            </p>
            <p>
              O produto pode ter sido salvo para monitoramento. Quando o backend encontrar
              uma oferta real que atinja a meta ou fique próxima dela, o alerta por email
              poderá ser enviado.
            </p>
            {dados.analise && <p>{dados.analise}</p>}
            <button className="new-search" onClick={onNovaBusca}>
              Fazer nova busca
            </button>
          </section>
        ) : (
          <>
            <section className="summary-grid">
              <Resumo
                label="Melhor preço real"
                value={formatarMoeda(melhor?.precoReal)}
                color={T.green}
              />
              <Resumo label="Loja destaque" value={melhor?.loja || "-"} />
              <Resumo label="Condição" value={melhor?.condicao || "-"} />
              <Resumo
                label="Status"
                value={melhor?.precoReal <= meta ? "Dentro da meta" : "Monitorando"}
                color={melhor?.precoReal <= meta ? T.green : T.orange}
              />
            </section>

            <div className="tabs">
              <button
                className={aba === "precos" ? "active" : ""}
                onClick={() => setAba("precos")}
              >
                💰 Preços reais
              </button>
              <button
                className={aba === "cupons" ? "active" : ""}
                onClick={() => setAba("cupons")}
              >
                🎟️ Possíveis cupons
              </button>
            </div>

            {aba === "precos" && (
              <div className="result-layout">
                <section className="cards-grid">
                  {resultados.map((r, index) => {
                    const loja = lojaInfo[r.loja_id] || {
                      cor: T.cyan,
                      bg: T.cyanDim,
                    };

                    const atingiu = r.precoReal <= meta;
                    const selecionada = lojaAtiva === r.loja_id;
                    const eBusca = r.link_tipo === "busca";

                    return (
                      <article
                        key={`${r.loja_id}-${index}`}
                        className={`price-card ${selecionada ? "selected" : ""}`}
                        onClick={() => setLojaAtiva(r.loja_id)}
                        style={{
                          borderColor: selecionada ? `${loja.cor}80` : undefined,
                          boxShadow: selecionada ? `0 0 24px ${loja.cor}16` : undefined,
                        }}
                      >
                        <div className="card-chips">
                          <LojaTag id={r.loja_id} nome={r.loja} />
                          {index === 0 && <Chip color={T.green}>🏆 Melhor</Chip>}
                          {atingiu && <Chip color={T.green}>✅ Meta</Chip>}
                          {eBusca ? (
                            <Chip color={T.orange}>🔍 Busca da loja</Chip>
                          ) : (
                            <Chip color={T.green}>🔗 Produto direto</Chip>
                          )}
                        </div>

                        <div className="price-value">{formatarMoeda(r.precoReal)}</div>

                        <div className="product-title">
                          {r.condicao} · {r.titulo || "Produto encontrado"}
                        </div>

                        {r.melhor_cupom && (
                          <div className="coupon-line">
                            🎟️ Possível cupom: <b>{r.melhor_cupom.codigo}</b>
                          </div>
                        )}

                        {r.melhor_cupom && (
                          <div className="coupon-warning">
                            Cupom não confirmado. Não foi aplicado ao preço.
                          </div>
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
                            {eBusca ? "Abrir busca →" : "Abrir produto →"}
                          </a>
                        ) : (
                          <div className="no-link">Link não encontrado</div>
                        )}
                      </article>
                    );
                  })}
                </section>

                <section className="chart-card">
                  <div className="chart-header">
                    <div>
                      {ativo && <LojaTag id={ativo.loja_id} nome={ativo.loja} />}
                      <h2>Histórico real</h2>
                    </div>

                    {ativo?.url && (
                      <a
                        href={ativo.url}
                        target="_blank"
                        rel="noreferrer"
                        className="chart-link"
                        style={{ background: lojaConf.cor || T.cyan }}
                      >
                        {ativo.link_tipo === "busca" ? "Abrir busca →" : "Abrir produto →"}
                      </a>
                    )}
                  </div>

                  {ativo?.historico?.length > 0 ? (
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
                  ) : (
                    <div style={{ color: T.muted, lineHeight: 1.6 }}>
                      Ainda não há histórico real suficiente para gerar gráfico. Ele aparecerá
                      conforme o monitoramento salvar novas verificações.
                    </div>
                  )}
                </section>
              </div>
            )}

            {aba === "cupons" && (
              <section className="coupon-panel">
                <h2>Possíveis cupons</h2>
                <p>
                  Cupons não são aplicados no preço principal. Eles aparecem apenas como
                  candidatos para você testar no checkout.
                </p>

                <div className="coupon-grid">
                  {cupons.length === 0 && (
                    <div className="no-coupon">
                      Nenhum possível cupom retornado pelo backend.
                    </div>
                  )}

                  {cupons.map((cupom, index) => (
                    <article
                      className="coupon-card"
                      key={`cupom-${cupom.loja_id}-${cupom.codigo}-${index}`}
                    >
                      <LojaTag id={cupom.loja_id} nome={cupom.loja} />

                      <div className="coupon-code">
                        Cupom: <b>{cupom.codigo}</b>
                      </div>

                      <div>
                        Preço real: <b>{formatarMoeda(cupom.precoReal)}</b>
                      </div>

                      <div className="coupon-meta">
                        Confiança: <b>{cupom.confianca}</b> ·{" "}
                        {cupom.verificado ? "verificado" : "não verificado"}
                      </div>

                      <p>{cupom.condicao}</p>
                      <p>{cupom.aviso}</p>

                      {cupom.url && (
                        <a href={cupom.url} target="_blank" rel="noreferrer">
                          Testar no checkout →
                        </a>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            )}

            {dados.analise && (
              <section className="analysis-card">
                <div>🤖 Análise automática</div>
                <p>{dados.analise}</p>
              </section>
            )}
          </>
        )}
      </div>
    </main>
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
        headers: { "Content-Type": "application/json" },
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

      if (!response.ok) {
        throw new Error(`Erro HTTP ${response.status}`);
      }

      const data = await response.json();

      setDados({
        ...data,
        resultados: normalizarResultadosBackend(data.resultados),
      });

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
