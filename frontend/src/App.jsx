import { useState, useRef, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

// ─── Tema ─────────────────────────────────────────────────────────────────────
const T = {
  bg:         "#07080f",
  card:       "#0e1120",
  cardAlt:    "#141828",
  border:     "#1c2540",
  borderHi:   "#2a3a6a",
  cyan:       "#00d4ff",
  cyanDim:    "#00d4ff18",
  green:      "#00e676",
  greenDim:   "#00e67618",
  orange:     "#ffab40",
  orangeDim:  "#ffab4018",
  red:        "#ff5252",
  purple:     "#ce93d8",
  purpleDim:  "#ce93d818",
  text:       "#dde3f5",
  muted:      "#4a5568",
  dim:        "#2d3748",
};

// ─── Base de cupons conhecidos por loja ──────────────────────────────────────
const CUPONS_BASE = {
  mercadolivre: [
    { codigo: "MELI5",       desc_pct: 5,   desc_fixo: 0,   condicao: "Qualquer compra",            tipo: "percentual" },
    { codigo: "MELIBEM",     desc_pct: 10,  desc_fixo: 0,   condicao: "Primeira compra do mês",     tipo: "percentual" },
    { codigo: "APPML10",     desc_pct: 10,  desc_fixo: 0,   condicao: "Compra pelo app",            tipo: "percentual" },
    { codigo: "FRETEGRATIS", desc_pct: 0,   desc_fixo: 0,   condicao: "Frete grátis selecionados",  tipo: "frete" },
  ],
  amazon: [
    { codigo: "PRIMEIRACOMPRA", desc_pct: 5,  desc_fixo: 0,  condicao: "Primeira compra Amazon",    tipo: "percentual" },
    { codigo: "PRIME30",        desc_pct: 0,  desc_fixo: 30, condicao: "Assinantes Prime",          tipo: "fixo" },
    { codigo: "APP10",          desc_pct: 10, desc_fixo: 0,  condicao: "Compra pelo app Amazon",    tipo: "percentual" },
  ],
  kabum: [
    { codigo: "KABUM10",    desc_pct: 10, desc_fixo: 0,  condicao: "Boleto/Pix",                    tipo: "percentual" },
    { codigo: "PRIMEIRAOL", desc_pct: 5,  desc_fixo: 0,  condicao: "Primeira compra Kabum",         tipo: "percentual" },
    { codigo: "KABUM5",     desc_pct: 5,  desc_fixo: 0,  condicao: "Qualquer compra",               tipo: "percentual" },
    { codigo: "KBMAGIC15",  desc_pct: 15, desc_fixo: 0,  condicao: "Produtos selecionados",         tipo: "percentual" },
  ],
  magalu: [
    { codigo: "PRIMEIRACOMPRA", desc_pct: 5,  desc_fixo: 0,  condicao: "Primeira compra Magalu",    tipo: "percentual" },
    { codigo: "APP15",          desc_pct: 15, desc_fixo: 0,  condicao: "App Magalu – novos usuários",tipo: "percentual" },
    { codigo: "LUIZA10",        desc_pct: 10, desc_fixo: 0,  condicao: "Compras acima de R$ 299",   tipo: "percentual" },
    { codigo: "PIX5",           desc_pct: 5,  desc_fixo: 0,  condicao: "Pagamento via Pix",         tipo: "percentual" },
  ],
  olx: [
    { codigo: "OLX30",    desc_pct: 0, desc_fixo: 30, condicao: "Primeira compra OLX (produto novo)", tipo: "fixo" },
    { codigo: "OLX20OFF", desc_pct: 0, desc_fixo: 20, condicao: "Cupom recorrente OLX",              tipo: "fixo" },
    { codigo: "OLXAPP",   desc_pct: 5, desc_fixo: 0,  condicao: "Compra pelo app OLX",               tipo: "percentual" },
  ],
  enjoei: [
    { codigo: "PRIMEIROENJOI", desc_pct: 10, desc_fixo: 0,  condicao: "Primeira compra Enjoei",     tipo: "percentual" },
    { codigo: "FRETEGRATIS",   desc_pct: 0,  desc_fixo: 0,  condicao: "Frete grátis selecionados",  tipo: "frete" },
  ],
};

const LOJAS_CONFIG = [
  { id: "mercadolivre", nome: "Mercado Livre", cor: "#ffe600", bg: "#ffe60015", emoji: "🛒", tag: "Novo" },
  { id: "amazon",       nome: "Amazon",        cor: "#ff9900", bg: "#ff990015", emoji: "📦", tag: "Novo" },
  { id: "kabum",        nome: "KaBuM!",         cor: "#f04e23", bg: "#f04e2315", emoji: "🖥️", tag: "Novo" },
  { id: "magalu",       nome: "Magalu",         cor: "#0086ff", bg: "#0086ff15", emoji: "🛍️", tag: "Novo" },
  { id: "olx",          nome: "OLX",            cor: "#9adc00", bg: "#9adc0015", emoji: "🏷️", tag: "Usado/Novo" },
  { id: "enjoei",       nome: "Enjoei",         cor: "#ff69b4", bg: "#ff69b415", emoji: "✨", tag: "Usado" },
];

function calcPrecoFinal(preco, cupom) {
  if (!cupom) return preco;
  if (cupom.tipo === "percentual") return preco * (1 - cupom.desc_pct / 100);
  if (cupom.tipo === "fixo") return Math.max(0, preco - cupom.desc_fixo);
  return preco;
}

function melhorCupom(lojaId, preco) {
  const cupons = CUPONS_BASE[lojaId] || [];
  let melhor = null, melhorPreco = preco;
  for (const c of cupons) {
    if (c.tipo === "frete") continue;
    const final = calcPrecoFinal(preco, c);
    if (final < melhorPreco) { melhorPreco = final; melhor = c; }
  }
  return melhor;
}

function gerarHistorico(base, dias = 21) {
  let p = base * 1.15;
  const hoje = new Date();
  return Array.from({ length: dias }, (_, i) => {
    p *= 1 + (Math.random() * 0.07 - 0.035);
    const d = new Date(hoje); d.setDate(d.getDate() - (dias - 1 - i));
    return { data: d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }), preco: parseFloat(p.toFixed(2)) };
  });
}

// ─── Claude API ───────────────────────────────────────────────────────────────
async function buscarPrecosIA(nome, meta) {
  const prompt = `Você é um assistente de comparação de preços brasileiro especializado.

Produto: "${nome}"
Meta do usuário: R$ ${meta}

Simule preços realistas do mercado brasileiro atual para esse produto nas 6 lojas abaixo.
Para OLX e Enjoei, simule preços de produtos usados/seminovos (tipicamente 20-40% mais baratos que o novo).

Retorne APENAS JSON puro, sem markdown, sem texto extra:
{
  "produto_normalizado": "nome limpo",
  "resultados": [
    {
      "loja_id": "mercadolivre",
      "preco": 0000.00,
      "preco_parcelado": "12x de R$ 000,00 sem juros",
      "frete": "Grátis",
      "condicao": "Novo",
      "disponivel": true,
      "url": "https://lista.mercadolivre.com.br/PRODUTO"
    },
    {
      "loja_id": "amazon",
      "preco": 0000.00,
      "preco_parcelado": "12x de R$ 000,00 sem juros",
      "frete": "Grátis Prime",
      "condicao": "Novo",
      "disponivel": true,
      "url": "https://www.amazon.com.br/s?k=PRODUTO"
    },
    {
      "loja_id": "kabum",
      "preco": 0000.00,
      "preco_parcelado": "12x de R$ 000,00 sem juros",
      "frete": "Grátis acima R$299",
      "condicao": "Novo",
      "disponivel": true,
      "url": "https://www.kabum.com.br/busca/PRODUTO"
    },
    {
      "loja_id": "magalu",
      "preco": 0000.00,
      "preco_parcelado": "10x de R$ 000,00 sem juros",
      "frete": "Grátis",
      "condicao": "Novo",
      "disponivel": true,
      "url": "https://www.magazineluiza.com.br/busca/PRODUTO/"
    },
    {
      "loja_id": "olx",
      "preco": 0000.00,
      "preco_parcelado": "À vista",
      "frete": "Combinar com vendedor",
      "condicao": "Usado – Bom estado",
      "disponivel": true,
      "url": "https://www.olx.com.br/brasil?q=PRODUTO"
    },
    {
      "loja_id": "enjoei",
      "preco": 0000.00,
      "preco_parcelado": "3x sem juros",
      "frete": "R$ 15,00 a R$ 25,00",
      "condicao": "Seminovo",
      "disponivel": true,
      "url": "https://www.enjoei.com.br/busca?q=PRODUTO"
    }
  ],
  "analise": "3 frases: onde está o melhor negócio novo, melhor usado, e se vale esperar ou comprar agora considerando a meta de R$ ${meta}"
}`;

  const resp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 1000,
      messages: [{ role: "user", content: prompt }],
    }),
  });
  const data = await resp.json();
  const raw = data.content?.find(b => b.type === "text")?.text || "{}";
  return JSON.parse(raw.replace(/```json|```/g, "").trim());
}

// ─── Sub-componentes ──────────────────────────────────────────────────────────
const Chip = ({ children, color = T.cyan, bg, style = {} }) => (
  <span style={{
    background: bg || color + "20", color, fontSize: 10, fontWeight: 700,
    padding: "3px 8px", borderRadius: 20, border: `1px solid ${color}30`,
    whiteSpace: "nowrap", letterSpacing: 0.3, ...style,
  }}>{children}</span>
);

function LojaTag({ id }) {
  const l = LOJAS_CONFIG.find(x => x.id === id);
  if (!l) return null;
  return <Chip color={l.cor} bg={l.bg}>{l.emoji} {l.nome}</Chip>;
}

function BarraProgresso({ preco, meta, cor }) {
  const pct = Math.min(100, (meta / preco) * 100);
  const atingiu = preco <= meta;
  return (
    <div style={{ height: 5, background: T.border, borderRadius: 4, overflow: "hidden", marginTop: 8 }}>
      <div style={{
        height: "100%", width: `${pct}%`,
        background: atingiu
          ? `linear-gradient(90deg, ${T.green}, #00bfa5)`
          : `linear-gradient(90deg, ${cor}cc, ${cor}55)`,
        borderRadius: 4, transition: "width .7s ease",
      }} />
    </div>
  );
}

function CupomCard({ cupom, precoBase, meta, lojaId }) {
  const loja = LOJAS_CONFIG.find(l => l.id === lojaId);
  const precoFinal = calcPrecoFinal(precoBase, cupom);
  const atingiu = precoFinal <= meta;
  const economia = precoBase - precoFinal;

  const icone = cupom.tipo === "frete" ? "🚚" : cupom.tipo === "fixo" ? "💵" : "🏷️";
  const descLabel = cupom.tipo === "percentual"
    ? `-${cupom.desc_pct}%`
    : cupom.tipo === "fixo"
    ? `-R$ ${cupom.desc_fixo}`
    : "Frete grátis";

  return (
    <div style={{
      background: atingiu ? T.greenDim : T.cardAlt,
      border: `1px solid ${atingiu ? T.green + "44" : T.border}`,
      borderRadius: 10, padding: "10px 13px",
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3, flexWrap: "wrap" }}>
          <span style={{
            fontFamily: "monospace", background: loja?.bg, color: loja?.cor,
            border: `1px solid ${loja?.cor}44`, borderRadius: 6,
            padding: "2px 8px", fontSize: 12, fontWeight: 800, letterSpacing: 1,
          }}>{cupom.codigo}</span>
          <Chip color={atingiu ? T.green : T.orange}>{descLabel}</Chip>
          {atingiu && <Chip color={T.green}>✅ Bate meta!</Chip>}
        </div>
        <div style={{ fontSize: 11, color: T.muted, marginBottom: 2 }}>{icone} {cupom.condicao}</div>
        {economia > 0 && (
          <div style={{ fontSize: 11, color: T.text }}>
            Preço final:{" "}
            <b style={{ color: atingiu ? T.green : loja?.cor }}>
              R$ {precoFinal.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
            </b>
            {" "}— economia de R$ {economia.toFixed(2)}
          </div>
        )}
      </div>
      <button
        onClick={() => navigator.clipboard?.writeText(cupom.codigo)}
        style={{
          background: loja?.bg, border: `1px solid ${loja?.cor}44`,
          color: loja?.cor, borderRadius: 7, padding: "6px 10px",
          fontSize: 11, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap",
          fontFamily: "inherit",
        }}
      >
        Copiar
      </button>
    </div>
  );
}

function TooltipChart({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 12px", fontSize: 12 }}>
      <div style={{ color: T.muted }}>{label}</div>
      <div style={{ color: T.cyan, fontWeight: 700 }}>R$ {payload[0].value.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</div>
    </div>
  );
}

// ─── Tela de Busca ────────────────────────────────────────────────────────────
function TelaBusca({ onBuscar, carregando, erro }) {
  const [nome, setNome] = useState("");
  const [meta, setMeta] = useState("");
  const ref = useRef(); useEffect(() => ref.current?.focus(), []);
  const ok = nome.trim() && meta && !carregando;

  return (
    <div style={{
      minHeight: "100vh", background: T.bg, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", padding: 24,
      fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
    }}>
      {/* glow */}
      <div style={{
        position: "fixed", top: "15%", left: "50%", transform: "translateX(-50%)",
        width: 600, height: 400,
        background: `radial-gradient(ellipse, ${T.cyan}0d 0%, transparent 65%)`,
        pointerEvents: "none",
      }} />

      <div style={{ textAlign: "center", marginBottom: 36, zIndex: 1 }}>
        <div style={{ fontSize: 44, marginBottom: 10 }}>🎯</div>
        <h1 style={{ margin: 0, fontSize: 30, fontWeight: 900, color: T.text, letterSpacing: -1 }}>
          Monitor de <span style={{ color: T.cyan }}>Preços</span>
        </h1>
        <p style={{ color: T.muted, fontSize: 13, margin: "8px 0 0" }}>
          Compara preços + cupons automáticos em 6 lojas
        </p>
      </div>

      <div style={{
        background: T.card, border: `1px solid ${T.border}`, borderRadius: 20,
        padding: 26, width: "100%", maxWidth: 400, zIndex: 1,
        boxShadow: `0 0 80px ${T.cyan}08`,
      }}>
        {[
          { key: "nome", label: "Produto", ph: "Ex: RTX 4070 Super, iPhone 15...", type: "text", ref },
          { key: "meta", label: "Meu preço meta (R$)", ph: "Ex: 3200", type: "number", ref: null },
        ].map(f => (
          <div key={f.key} style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 10, fontWeight: 700, color: T.muted, textTransform: "uppercase", letterSpacing: 1, display: "block", marginBottom: 6 }}>
              {f.label}
            </label>
            <input
              ref={f.ref}
              value={f.key === "nome" ? nome : meta}
              onChange={e => f.key === "nome" ? setNome(e.target.value) : setMeta(e.target.value)}
              onKeyDown={e => e.key === "Enter" && ok && onBuscar(nome.trim(), parseFloat(meta))}
              placeholder={f.ph}
              type={f.type}
              style={{
                width: "100%", boxSizing: "border-box",
                background: T.bg, border: `1.5px solid ${T.border}`,
                borderRadius: 11, padding: "12px 14px",
                color: T.text, fontSize: 14, outline: "none", fontFamily: "inherit",
              }}
              onFocus={e => e.target.style.borderColor = T.cyan}
              onBlur={e => e.target.style.borderColor = T.border}
            />
          </div>
        ))}

        <button
          onClick={() => ok && onBuscar(nome.trim(), parseFloat(meta))}
          disabled={!ok}
          style={{
            width: "100%", padding: "13px 0", marginTop: 4,
            background: ok ? `linear-gradient(135deg, ${T.cyan}, #007ea8)` : T.border,
            color: ok ? "#000" : T.muted,
            border: "none", borderRadius: 11, fontSize: 14, fontWeight: 800,
            cursor: ok ? "pointer" : "not-allowed", fontFamily: "inherit",
          }}
        >
          {carregando ? "🔍 Buscando em 6 lojas..." : "🔍 Buscar preços e cupons"}
        </button>

        {erro && <div style={{ marginTop: 12, color: T.red, fontSize: 12, textAlign: "center" }}>{erro}</div>}

        <div style={{ marginTop: 18, display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center" }}>
          {LOJAS_CONFIG.map(l => (
            <span key={l.id} style={{ fontSize: 10, color: l.cor, background: l.bg, padding: "3px 9px", borderRadius: 20, border: `1px solid ${l.cor}30` }}>
              {l.emoji} {l.nome} <span style={{ opacity: .6 }}>{l.tag}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Painel de Resultado ──────────────────────────────────────────────────────
function PainelResultado({ dados, meta, onNovaBusca }) {
  const { produto_normalizado, resultados, analise, historicos } = dados;
  const [lojaAtiva, setLojaAtiva] = useState(null);
  const [abaAtiva, setAbaAtiva] = useState("precos"); // "precos" | "cupons"

  // Enriquece resultados com cupons
  const resultadosEnriquecidos = resultados.map(r => {
    const cupons = CUPONS_BASE[r.loja_id] || [];
    const mc = melhorCupom(r.loja_id, r.preco);
    return {
      ...r,
      cupons,
      melhorCupom: mc,
      precoComMelhorCupom: mc ? calcPrecoFinal(r.preco, mc) : null,
    };
  });

  const ordenados = [...resultadosEnriquecidos].sort((a, b) => {
    const pa = a.precoComMelhorCupom ?? a.preco;
    const pb = b.precoComMelhorCupom ?? b.preco;
    return pa - pb;
  });

  const melhorGeral = ordenados[0];
  useEffect(() => { setLojaAtiva(melhorGeral?.loja_id); }, []);

  const ativo = resultadosEnriquecidos.find(r => r.loja_id === lojaAtiva) || melhorGeral;
  const lojaConf = LOJAS_CONFIG.find(l => l.id === ativo?.loja_id);

  // Todos os cupons que batem a meta
  const cuponsQueBatemMeta = resultadosEnriquecidos.flatMap(r =>
    (r.cupons || [])
      .filter(c => c.tipo !== "frete" && calcPrecoFinal(r.preco, c) <= meta)
      .map(c => ({ ...c, loja_id: r.loja_id, preco_base: r.preco, preco_final: calcPrecoFinal(r.preco, c) }))
  ).sort((a, b) => a.preco_final - b.preco_final);

  return (
    <div style={{
      minHeight: "100vh", background: T.bg, padding: "18px 14px",
      fontFamily: "'DM Sans', 'Segoe UI', sans-serif", color: T.text,
    }}>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 10, color: T.muted, textTransform: "uppercase", letterSpacing: 1 }}>🎯 Monitorando</div>
          <h2 style={{ margin: "4px 0 2px", fontSize: 17, fontWeight: 800 }}>{produto_normalizado}</h2>
          <div style={{ fontSize: 12, color: T.muted }}>
            Meta: <b style={{ color: T.cyan }}>R$ {meta.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</b>
            {cuponsQueBatemMeta.length > 0 && (
              <span style={{ marginLeft: 8, color: T.green }}>
                🎟️ {cuponsQueBatemMeta.length} cupom{cuponsQueBatemMeta.length > 1 ? "s" : ""} batem a meta!
              </span>
            )}
          </div>
        </div>
        <button onClick={onNovaBusca} style={{
          background: T.cardAlt, border: `1px solid ${T.border}`, color: T.muted,
          borderRadius: 9, padding: "7px 12px", fontSize: 11, fontWeight: 700,
          cursor: "pointer", fontFamily: "inherit",
        }}>+ Nova busca</button>
      </div>

      {/* Abas */}
      <div style={{ display: "flex", gap: 6, marginBottom: 14, background: T.card, borderRadius: 10, padding: 4 }}>
        {[
          { id: "precos", label: "💰 Preços" },
          { id: "cupons", label: `🎟️ Cupons${cuponsQueBatemMeta.length ? ` (${cuponsQueBatemMeta.length} ✅)` : ""}` },
        ].map(a => (
          <button key={a.id} onClick={() => setAbaAtiva(a.id)} style={{
            flex: 1, padding: "8px 0", borderRadius: 8, border: "none", cursor: "pointer",
            fontWeight: 700, fontSize: 12, fontFamily: "inherit",
            background: abaAtiva === a.id ? T.cardAlt : "transparent",
            color: abaAtiva === a.id ? T.text : T.muted,
            boxShadow: abaAtiva === a.id ? `0 1px 6px #00000033` : "none",
          }}>{a.label}</button>
        ))}
      </div>

      {/* Aba Preços */}
      {abaAtiva === "precos" && (
        <>
          {/* Cards de lojas */}
          <div style={{ display: "flex", flexDirection: "column", gap: 9, marginBottom: 14 }}>
            {ordenados.map((r, i) => {
              const loja = LOJAS_CONFIG.find(l => l.id === r.loja_id);
              const precoEfetivo = r.precoComMelhorCupom ?? r.preco;
              const atingiu = precoEfetivo <= meta;
              const ativo = lojaAtiva === r.loja_id;

              return (
                <div key={r.loja_id} onClick={() => setLojaAtiva(r.loja_id)} style={{
                  background: ativo ? T.cardAlt : T.card,
                  border: `1.5px solid ${ativo ? loja?.cor + "55" : T.border}`,
                  borderRadius: 13, padding: "13px 15px", cursor: "pointer",
                  boxShadow: ativo ? `0 0 18px ${loja?.cor}14` : "none",
                  transition: "all .2s",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 4 }}>
                        <LojaTag id={r.loja_id} />
                        {i === 0 && <Chip color={T.green}>🏆 Melhor negócio</Chip>}
                        {r.condicao?.toLowerCase().includes("usado") || r.condicao?.toLowerCase().includes("semi") ? (
                          <Chip color={T.purple}>♻️ {r.condicao}</Chip>
                        ) : null}
                      </div>
                      <div style={{ fontSize: 11, color: T.muted }}>{r.frete} · {r.preco_parcelado}</div>
                      {r.melhorCupom && (
                        <div style={{ fontSize: 11, color: T.orange, marginTop: 3 }}>
                          🎟️ com <b style={{ fontFamily: "monospace" }}>{r.melhorCupom.codigo}</b>: R$ {precoEfetivo.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                        </div>
                      )}
                    </div>
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                      {r.melhorCupom && (
                        <div style={{ fontSize: 11, color: T.muted, textDecoration: "line-through" }}>
                          R$ {r.preco.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                        </div>
                      )}
                      <div style={{ fontSize: 19, fontWeight: 900, color: atingiu ? T.green : T.text }}>
                        R$ {precoEfetivo.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </div>
                      {atingiu && <Chip color={T.green} style={{ fontSize: 9 }}>✅ Meta!</Chip>}
                    </div>
                  </div>
                  <BarraProgresso preco={precoEfetivo} meta={meta} cor={loja?.cor || T.cyan} />
                </div>
              );
            })}
          </div>

          {/* Detalhe da loja ativa */}
          {ativo && (
            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 14, padding: 16, marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <LojaTag id={ativo.loja_id} />
                <a href={ativo.url} target="_blank" rel="noreferrer" style={{
                  background: lojaConf?.cor, color: "#000", padding: "6px 14px",
                  borderRadius: 7, fontSize: 11, fontWeight: 700, textDecoration: "none",
                }}>Ver no site →</a>
              </div>

              {/* Gráfico */}
              <div style={{ fontSize: 11, color: T.muted, marginBottom: 6 }}>📈 Histórico estimado (21 dias)</div>
              <ResponsiveContainer width="100%" height={110}>
                <LineChart data={historicos[ativo.loja_id]}>
                  <XAxis dataKey="data" tick={{ fontSize: 9, fill: T.dim }} axisLine={false} tickLine={false} interval={4} />
                  <YAxis hide domain={["auto", "auto"]} />
                  <Tooltip content={<TooltipChart />} />
                  <ReferenceLine y={meta} stroke={T.green} strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="preco" stroke={lojaConf?.cor || T.cyan} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}

      {/* Aba Cupons */}
      {abaAtiva === "cupons" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Cupons que batem a meta — destaque */}
          {cuponsQueBatemMeta.length > 0 && (
            <div style={{ background: T.greenDim, border: `1px solid ${T.green}33`, borderRadius: 14, padding: 14 }}>
              <div style={{ fontSize: 11, color: T.green, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 10 }}>
                ✅ Cupons que atingem sua meta
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {cuponsQueBatemMeta.map((c, i) => (
                  <CupomCard key={i} cupom={c} precoBase={c.preco_base} meta={meta} lojaId={c.loja_id} />
                ))}
              </div>
            </div>
          )}

          {/* Todos os cupons por loja */}
          {LOJAS_CONFIG.map(loja => {
            const resultado = resultadosEnriquecidos.find(r => r.loja_id === loja.id);
            if (!resultado) return null;
            const cupons = CUPONS_BASE[loja.id] || [];
            return (
              <div key={loja.id} style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 14, padding: 14 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <LojaTag id={loja.id} />
                  <span style={{ fontSize: 12, color: T.muted }}>
                    Preço: <b style={{ color: T.text }}>R$ {resultado.preco.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</b>
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {cupons.map((c, i) => (
                    <CupomCard key={i} cupom={c} precoBase={resultado.preco} meta={meta} lojaId={loja.id} />
                  ))}
                  {cupons.length === 0 && (
                    <div style={{ fontSize: 12, color: T.muted, textAlign: "center", padding: "10px 0" }}>
                      Nenhum cupom mapeado para esta loja.
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Análise IA */}
      {analise && (
        <div style={{
          background: T.cyanDim, border: `1px solid ${T.cyan}28`,
          borderRadius: 13, padding: "13px 15px", marginTop: 14,
        }}>
          <div style={{ fontSize: 10, color: T.cyan, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 6 }}>
            🤖 Análise IA
          </div>
          <p style={{ margin: 0, fontSize: 13, color: T.text, lineHeight: 1.7 }}>{analise}</p>
        </div>
      )}
    </div>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [tela, setTela] = useState("busca");
  const [carregando, setCarregando] = useState(false);
  const [dados, setDados] = useState(null);
  const [metaAtual, setMetaAtual] = useState(0);
  const [erro, setErro] = useState("");

  const handleBuscar = async (nome, meta) => {
    setCarregando(true); setErro("");
    try {
      const res = await buscarPrecosIA(nome, meta);
      const historicos = {};
      (res.resultados || []).forEach(r => { historicos[r.loja_id] = gerarHistorico(r.preco, 21); });
      setDados({ ...res, historicos });
      setMetaAtual(meta);
      setTela("resultado");
    } catch (e) {
      setErro("Erro ao buscar. Tente novamente.");
    } finally {
      setCarregando(false);
    }
  };

  if (tela === "resultado" && dados)
    return <PainelResultado dados={dados} meta={metaAtual} onNovaBusca={() => setTela("busca")} />;

  return <TelaBusca onBuscar={handleBuscar} carregando={carregando} erro={erro} />;
}
