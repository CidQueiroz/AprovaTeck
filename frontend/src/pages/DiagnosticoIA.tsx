import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useAI } from '../context/AIContext';
import { supabase } from '../config/supabase';
import { generateAIAnswer } from '../services/aiService';
import { BrainCircuit, Sparkles, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export const DiagnosticoIA: React.FC = () => {
  const { user } = useAuth();
  const { keys, preferredBanca } = useAI();
  const [periodo, setPeriodo] = useState('7');
  const [loading, setLoading] = useState(false);
  const [diagnostico, setDiagnostico] = useState<string | null>(null);
  const [statsPeriodo, setStatsPeriodo] = useState<{ total: number; acertos: number; taxa: number } | null>(null);

  const gerarDiagnostico = async () => {
    if (!user) return;
    setLoading(true);
    setDiagnostico(null);

    try {
      const dias = parseInt(periodo, 10);
      const dataCorte = new Date();
      dataCorte.setDate(dataCorte.getDate() - dias);

      const { data: historico } = await supabase
        .from('respostas')
        .select(`
          acertou,
          questoes!inner(
            enunciado,
            gabarito,
            itens_estudo!inner(
              nome,
              subgrupos!inner(
                nome,
                grupos!inner(nome)
              )
            )
          )
        `)
        .eq('user_id', user.id)
        .gte('data', dataCorte.toISOString());

      if (!historico || historico.length < 3) {
        alert('Histórico insuficiente no período selecionado (mínimo 3 questões respondidas). Faça mais questões no Modo Prova ou no POD!');
        setLoading(false);
        return;
      }

      const total = historico.length;
      const acertos = historico.filter((r: any) => r.acertou).length;
      const taxa = Math.round((acertos / total) * 100);
      setStatsPeriodo({ total, acertos, taxa });

      // Agrupar erros
      const errosPorMateria: { [key: string]: { total: number; erros: number } } = {};
      historico.forEach((r: any) => {
        const mat = r.questoes?.itens_estudo?.subgrupos?.grupos?.nome || 'Geral';
        if (!errosPorMateria[mat]) errosPorMateria[mat] = { total: 0, erros: 0 };
        errosPorMateria[mat].total += 1;
        if (!r.acertou) errosPorMateria[mat].erros += 1;
      });

      const resumoPerformance = Object.entries(errosPorMateria)
        .map(([m, dados]) => `- ${m}: ${dados.total} questões respondidas, taxa de erro de ${Math.round((dados.erros / dados.total) * 100)}%`)
        .join('\n');

      const prompt = `Analise o seguinte desempenho do concurseiro nos últimos ${periodo} dias:\nTotal de questões: ${total}\nTaxa de acerto global: ${taxa}%\n\nDesempenho por Matéria:\n${resumoPerformance}\n\nForneça: 1) Diagnóstico dos Pontos Críticos e Vulnerabilidades; 2) Sugestão de ajuste no ritmo de estudos; 3) Plano de Ação Estratégico para os próximos 7 dias focado na banca ${preferredBanca}.`;

      const res = await generateAIAnswer(keys, prompt, `Você é o Tutor-Chefe da AprovaTeck, especialista em neurociência do aprendizado e bancas de concurso.`);

      if (res.content) {
        setDiagnostico(res.content);
      } else {
        setDiagnostico(res.error || 'Erro ao gerar diagnóstico.');
      }
    } catch (err) {
      console.error('Erro ao gerar diagnóstico:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '1.6rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BrainCircuit size={26} color="#ec4899" /> Conselho do Tutor: Diagnóstico de Evolução 🤖🩺
        </h1>
        <p style={{ color: 'var(--cor-texto-muted)', fontSize: '0.9rem' }}>
          Identifique seus padrões de erro e receba um plano de ação cirúrgico gerado por inteligência artificial.
        </p>
      </div>

      <div className="glass-card" style={{ padding: '28px', marginBottom: '28px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '220px' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--cor-texto-muted)', marginBottom: '6px' }}>
              Período de Análise
            </label>
            <select
              value={periodo}
              onChange={e => setPeriodo(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid var(--border-color)',
                color: 'var(--cor-texto)',
                fontSize: '0.9rem',
                outline: 'none'
              }}
            >
              <option value="7" style={{ background: '#0e1117' }}>Últimos 7 dias</option>
              <option value="15" style={{ background: '#0e1117' }}>Últimos 15 dias</option>
              <option value="30" style={{ background: '#0e1117' }}>Últimos 30 dias</option>
              <option value="9999" style={{ background: '#0e1117' }}>Todo o histórico</option>
            </select>
          </div>

          <div style={{ alignSelf: 'flex-end' }}>
            <button
              onClick={gerarDiagnostico}
              disabled={loading}
              className="btn-sovereign btn-primary"
              style={{ padding: '11px 24px', fontSize: '0.9rem' }}
            >
              {loading ? (
                <>
                  <RefreshCw className="animate-spin" size={18} /> Analisando Dados...
                </>
              ) : (
                <>
                  <Sparkles size={18} /> Gerar Diagnóstico IA
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {statsPeriodo && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          marginBottom: '28px'
        }}>
          <div className="glass-card" style={{ padding: '18px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--cor-texto-muted)', display: 'block' }}>Questões no Período</span>
            <span style={{ fontSize: '1.4rem', fontWeight: 800 }}>{statsPeriodo.total}</span>
          </div>

          <div className="glass-card" style={{ padding: '18px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--cor-texto-muted)', display: 'block' }}>Acertos</span>
            <span style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--cor-secundaria)' }}>{statsPeriodo.acertos}</span>
          </div>

          <div className="glass-card" style={{ padding: '18px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--cor-texto-muted)', display: 'block' }}>Taxa de Aproveitamento</span>
            <span style={{ fontSize: '1.4rem', fontWeight: 800, color: statsPeriodo.taxa >= 70 ? '#22c55e' : '#f59e0b' }}>
              {statsPeriodo.taxa}%
            </span>
          </div>
        </div>
      )}

      {diagnostico && (
        <div className="glass-card" style={{ padding: '32px', border: '1px solid rgba(236, 72, 153, 0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'rgba(236, 72, 153, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ec4899'
            }}>
              <BrainCircuit size={22} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.2rem', margin: 0 }}>Parecer Oficial do Tutor IA</h3>
              <span style={{ fontSize: '0.75rem', color: 'var(--cor-texto-muted)' }}>Especialista Banca {preferredBanca}</span>
            </div>
          </div>

          <div style={{
            fontSize: '0.95rem',
            lineHeight: 1.8,
            color: 'var(--cor-texto)',
            whiteSpace: 'pre-wrap',
            background: 'rgba(0, 0, 0, 0.25)',
            padding: '24px',
            borderRadius: '12px',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            width: '100%',
            minWidth: 0,
            maxWidth: '100%',
            boxSizing: 'border-box',
            overflowX: 'auto',
            overflowWrap: 'anywhere',
            wordBreak: 'break-word'
          }}>
            <div className="ai-markdown-content">
              <ReactMarkdown>{diagnostico}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
