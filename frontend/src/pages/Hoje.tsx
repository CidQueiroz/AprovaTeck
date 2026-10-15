import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useAI } from '../context/AIContext';
import { montarPlanoDiario, processarResposta, salvarResumoItem, ItemEstudo } from '../services/schedulerService';
import { generateAIAnswer } from '../services/aiService';
import { supabase } from '../config/supabase';
import { CalendarCheck, Sparkles, CheckCircle2, XCircle, BookOpen, RefreshCw, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export const Hoje: React.FC = () => {
  const { user } = useAuth();
  const { keys } = useAI();
  const [novos, setNovos] = useState<ItemEstudo[]>([]);
  const [revisoes, setRevisoes] = useState<ItemEstudo[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeItem, setActiveItem] = useState<number | null>(null);

  // Estados de questões e resumos
  const [resumos, setResumos] = useState<{ [key: number]: string }>({});
  const [generatingResumo, setGeneratingResumo] = useState<number | null>(null);
  const [questoesPorItem, setQuestoesPorItem] = useState<{ [key: number]: any[] }>({});
  const [loadingQuestoes, setLoadingQuestoes] = useState<number | null>(null);
  const [respostasUsuario, setRespostasUsuario] = useState<{ [key: number]: { [qId: number]: { resposta: string; acertou: boolean } } }>({});

  const carregarPlano = async () => {
    if (!user) return;
    setLoading(true);
    const { novos: n, revisoes: r } = await montarPlanoDiario(user.id);
    setNovos(n);
    setRevisoes(r);
    
    // Carregar resumos existentes
    const resMap: { [key: number]: string } = {};
    [...n, ...r].forEach(it => {
      if (it.resumo) resMap[it.item_id] = it.resumo;
    });
    setResumos(resMap);
    setLoading(false);
  };

  useEffect(() => {
    carregarPlano();
  }, [user]);

  const carregarQuestoes = async (itemId: number) => {
    if (questoesPorItem[itemId]) return;
    setLoadingQuestoes(itemId);
    const { data } = await supabase
      .from('questoes')
      .select('*')
      .eq('item_id', itemId)
      .limit(3);

    setQuestoesPorItem(prev => ({ ...prev, [itemId]: data || [] }));
    setLoadingQuestoes(null);
  };

  const handleGerarResumo = async (item: ItemEstudo) => {
    if (!user) return;
    setGeneratingResumo(item.item_id);
    const prompt = `Gere um resumo esquemático, didático e cirúrgico para concurso público sobre o seguinte tópico:\nDisciplina: ${item.grupo_nome}\nAssunto: ${item.subgrupo_nome}\nTópico: ${item.item_nome}\n\nDestaque: 1) Conceito Essencial; 2) Pontos mais cobrados em provas; 3) Pegadinhas clássicas.`;
    const res = await generateAIAnswer(keys, prompt, 'Você é um professor mentor especialista em aprovação em concursos públicos de alto nível.');
    
    if (res.content) {
      setResumos(prev => ({ ...prev, [item.item_id]: res.content }));
      await salvarResumoItem(user.id, item.item_id, res.content);
    } else {
      alert(res.error || 'Erro ao gerar resumo.');
    }
    setGeneratingResumo(null);
  };

  const handleResponder = async (itemId: number, q: any, alternativa: string) => {
    if (!user) return;
    const acertou = alternativa.toUpperCase().trim() === q.gabarito.toUpperCase().trim();
    
    // 1. Salvar no Supabase
    await supabase.from('respostas').insert({
      user_id: user.id,
      questao_id: q.id,
      resposta_usuario: alternativa,
      acertou: acertou,
      data: new Date().toISOString()
    });

    // 2. Processar repetição espaçada
    await processarResposta(user.id, itemId, acertou);

    setRespostasUsuario(prev => ({
      ...prev,
      [itemId]: {
        ...(prev[itemId] || {}),
        [q.id]: { resposta: alternativa, acertou }
      }
    }));
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px' }}>
        <RefreshCw className="animate-spin" size={32} color="var(--cor-secundaria)" />
        <p style={{ marginTop: '16px', color: 'var(--cor-texto-muted)' }}>Montando seu Plano de Operações Diárias com AMV 2.0...</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.6rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CalendarCheck size={26} color="var(--cor-secundaria)" /> Plano de Operações Diárias (POD) 🎯
          </h1>
          <p style={{ color: 'var(--cor-texto-muted)', fontSize: '0.9rem' }}>
            Cronograma montado on-the-fly usando repetição espaçada (Spaced Repetition) e curva de esquecimento.
          </p>
        </div>

        <button
          onClick={carregarPlano}
          className="btn-sovereign btn-secondary"
          style={{ fontSize: '0.85rem' }}
        >
          <RefreshCw size={16} /> Atualizar Plano
        </button>
      </div>

      {/* BLOCO 1: NOVOS CONTEÚDOS */}
      <div style={{ marginBottom: '36px' }}>
        <h2 style={{ fontSize: '1.2rem', marginBottom: '16px', color: 'var(--cor-primaria)' }}>
          🆕 Apreensão de Conteúdo Novo ({novos.length})
        </h2>

        {novos.length === 0 ? (
          <div className="glass-card" style={{ padding: '24px', textAlign: 'center', color: 'var(--cor-texto-muted)' }}>
            <CheckCircle2 size={32} color="var(--cor-secundaria)" style={{ margin: '0 auto 10px auto' }} />
            Parabéns! Não há novos conteúdos pendentes para hoje.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {novos.map(item => (
              <div key={item.item_id} className="glass-card" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--cor-secundaria)', fontWeight: 700 }}>
                      {item.grupo_nome} ➔ {item.subgrupo_nome}
                    </span>
                    <h3 style={{ fontSize: '1.1rem', marginTop: '4px' }}>{item.item_nome}</h3>
                  </div>

                  <button
                    onClick={() => {
                      const next = activeItem === item.item_id ? null : item.item_id;
                      setActiveItem(next);
                      if (next) carregarQuestoes(item.item_id);
                    }}
                    className="btn-sovereign btn-secondary"
                    style={{ fontSize: '0.8rem' }}
                  >
                    {activeItem === item.item_id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    {activeItem === item.item_id ? 'Ocultar' : 'Estudar Tópico'}
                  </button>
                </div>

                {/* Área Expandida */}
                {activeItem === item.item_id && (
                  <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    {/* Botão de Resumo IA */}
                    <div style={{ marginBottom: '20px' }}>
                      <button
                        onClick={() => handleGerarResumo(item)}
                        disabled={generatingResumo === item.item_id}
                        className="btn-sovereign btn-primary"
                        style={{ fontSize: '0.85rem' }}
                      >
                        <Sparkles size={16} />
                        {generatingResumo === item.item_id ? 'Gerando Resumo com IA...' : resumos[item.item_id] ? 'Regerar Resumo IA' : 'Gerar Resumo Inteligente'}
                      </button>

                      {resumos[item.item_id] && (
                        <div style={{
                          marginTop: '14px',
                          padding: '18px',
                          borderRadius: '10px',
                          background: 'rgba(0, 0, 0, 0.3)',
                          border: '1px solid var(--border-color)',
                          fontSize: '0.9rem',
                          lineHeight: 1.6,
                          whiteSpace: 'pre-wrap',
                          width: '100%',
                          minWidth: 0,
                          maxWidth: '100%',
                          height: 'auto',
                          boxSizing: 'border-box',
                          overflowX: 'auto',
                          overflowY: 'visible',
                          overflowWrap: 'anywhere',
                          wordBreak: 'break-word'
                        }}>
                          <div className="ai-markdown-content">
                            <ReactMarkdown>{resumos[item.item_id]}</ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Questões de Fixação */}
                    <h4 style={{ fontSize: '0.95rem', marginBottom: '12px' }}>🎯 Questões de Fixação Imediata:</h4>
                    {loadingQuestoes === item.item_id ? (
                      <p style={{ color: 'var(--cor-texto-muted)', fontSize: '0.85rem' }}>Carregando questões...</p>
                    ) : questoesPorItem[item.item_id]?.length === 0 ? (
                      <p style={{ color: 'var(--cor-texto-muted)', fontSize: '0.85rem' }}>Nenhuma questão cadastrada para este tópico.</p>
                    ) : (
                      questoesPorItem[item.item_id]?.map(q => {
                        const resp = respostasUsuario[item.item_id]?.[q.id];
                        const hasMultipla = !!(q.alternativa_a || q.alternativa_b || q.alternativa_c || q.alternativa_d);
                        const altsMultipla = hasMultipla ? [
                          { key: 'A', text: q.alternativa_a },
                          { key: 'B', text: q.alternativa_b },
                          { key: 'C', text: q.alternativa_c },
                          { key: 'D', text: q.alternativa_d },
                          { key: 'E', text: q.alternativa_e },
                        ].filter(a => a.text && a.text.trim() !== '' && a.text !== 'N/A') : [];

                        return (
                          <div key={q.id} style={{
                            padding: '16px',
                            borderRadius: '10px',
                            background: 'rgba(0, 0, 0, 0.2)',
                            marginBottom: '16px',
                            border: '1px solid rgba(255, 255, 255, 0.05)'
                          }}>
                            <p style={{ fontSize: '0.95rem', marginBottom: '14px', lineHeight: 1.6 }}>{q.enunciado}</p>
                            
                            {hasMultipla && altsMultipla.length > 0 ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                {altsMultipla.map(alt => {
                                  const isSelected = resp?.resposta === alt.key;
                                  const isCorrect = q.gabarito?.trim().toUpperCase() === alt.key;
                                  let bg = 'rgba(0, 0, 0, 0.3)';
                                  let bColor = 'rgba(255, 255, 255, 0.1)';

                                  if (resp) {
                                    if (isSelected) {
                                      bg = isCorrect ? 'rgba(6, 240, 168, 0.2)' : 'rgba(239, 68, 68, 0.25)';
                                      bColor = isCorrect ? 'var(--cor-secundaria)' : '#ef4444';
                                    } else if (isCorrect) {
                                      bg = 'rgba(6, 240, 168, 0.15)';
                                      bColor = 'var(--cor-secundaria)';
                                    }
                                  }

                                  return (
                                    <button
                                      key={alt.key}
                                      disabled={!!resp}
                                      onClick={() => handleResponder(item.item_id, q, alt.key)}
                                      style={{
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        gap: '12px',
                                        padding: '12px 16px',
                                        borderRadius: '10px',
                                        border: `1px solid ${bColor}`,
                                        background: bg,
                                        color: '#ffffff',
                                        textAlign: 'left',
                                        fontSize: '0.9rem',
                                        lineHeight: 1.4,
                                        cursor: resp ? 'default' : 'pointer'
                                      }}
                                    >
                                      <span style={{
                                        width: '24px',
                                        height: '24px',
                                        borderRadius: '50%',
                                        background: isSelected ? 'var(--cor-primaria)' : 'rgba(255, 255, 255, 0.1)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontWeight: 800,
                                        fontSize: '0.8rem',
                                        flexShrink: 0
                                      }}>
                                        {alt.key}
                                      </span>
                                      <span style={{ flex: 1 }}>{alt.text}</span>
                                    </button>
                                  );
                                })}
                              </div>
                            ) : (
                              <div style={{ display: 'flex', gap: '10px' }}>
                                {['C', 'E'].map(alt => (
                                  <button
                                    key={alt}
                                    disabled={!!resp}
                                    onClick={() => handleResponder(item.item_id, q, alt)}
                                    style={{
                                      padding: '10px 20px',
                                      borderRadius: '8px',
                                      border: '1px solid rgba(255, 255, 255, 0.1)',
                                      background: resp?.resposta === alt 
                                        ? resp.acertou ? 'rgba(6, 240, 168, 0.25)' : 'rgba(239, 68, 68, 0.25)'
                                        : 'rgba(0, 0, 0, 0.3)',
                                      color: '#ffffff',
                                      fontWeight: 700,
                                      cursor: resp ? 'default' : 'pointer'
                                    }}
                                  >
                                    {alt === 'C' ? 'Certo' : 'Errado'}
                                  </button>
                                ))}
                              </div>
                            )}

                            {resp && (
                              <div style={{
                                marginTop: '12px',
                                fontSize: '0.85rem',
                                color: resp.acertou ? 'var(--cor-secundaria)' : '#f87171',
                                fontWeight: 600,
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px'
                              }}>
                                {resp.acertou ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                                {resp.acertou ? 'Resposta Correta! Registrado no AMV 2.0.' : `Incorreto. O gabarito é ${q.gabarito}. Reagendado para revisão amanhã.`}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* BLOCO 2: REVISÕES ESPAÇADAS */}
      <div>
        <h2 style={{ fontSize: '1.2rem', marginBottom: '16px', color: 'var(--cor-secundaria)' }}>
          🔄 Revisões AMV 2.0 do Dia ({revisoes.length})
        </h2>

        {revisoes.length === 0 ? (
          <div className="glass-card" style={{ padding: '24px', textAlign: 'center', color: 'var(--cor-texto-muted)' }}>
            <CheckCircle2 size={32} color="var(--cor-secundaria)" style={{ margin: '0 auto 10px auto' }} />
            Todas as revisões agendadas estão em dia!
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {revisoes.map(item => (
              <div key={item.item_id} className="glass-card" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--cor-secundaria)', fontWeight: 700 }}>
                      {item.grupo_nome} ➔ {item.subgrupo_nome}
                    </span>
                    <h3 style={{ fontSize: '1.1rem', marginTop: '4px' }}>{item.item_nome}</h3>
                    <span style={{ fontSize: '0.8rem', color: 'var(--cor-texto-muted)' }}>
                      Taxa de Acerto: {Math.round(item.taxa_acerto)}% | Estudado {item.vezes_estudado}x
                    </span>
                  </div>

                  <button
                    onClick={() => {
                      const next = activeItem === item.item_id ? null : item.item_id;
                      setActiveItem(next);
                      if (next) carregarQuestoes(item.item_id);
                    }}
                    className="btn-sovereign btn-secondary"
                    style={{ fontSize: '0.8rem' }}
                  >
                    {activeItem === item.item_id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    {activeItem === item.item_id ? 'Ocultar' : 'Revisar Agora'}
                  </button>
                </div>

                {/* Área de Revisão */}
                {activeItem === item.item_id && (
                  <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    {resumos[item.item_id] && (
                      <div style={{
                        marginBottom: '16px',
                        padding: '14px',
                        borderRadius: '8px',
                        background: 'rgba(0, 0, 0, 0.25)',
                        border: '1px solid var(--border-color)',
                        fontSize: '0.85rem'
                      }}>
                        <strong>💡 Resumo Esquematizado:</strong>
                        <p style={{ marginTop: '6px', whiteSpace: 'pre-line' }}>{resumos[item.item_id]}</p>
                      </div>
                    )}

                    <h4 style={{ fontSize: '0.95rem', marginBottom: '12px' }}>🎯 Questões de Fixação da Revisão:</h4>
                    {questoesPorItem[item.item_id]?.map(q => {
                      const resp = respostasUsuario[item.item_id]?.[q.id];
                      const hasMultipla = !!(q.alternativa_a || q.alternativa_b || q.alternativa_c || q.alternativa_d);
                      const altsMultipla = hasMultipla ? [
                        { key: 'A', text: q.alternativa_a },
                        { key: 'B', text: q.alternativa_b },
                        { key: 'C', text: q.alternativa_c },
                        { key: 'D', text: q.alternativa_d },
                        { key: 'E', text: q.alternativa_e },
                      ].filter(a => a.text && a.text.trim() !== '' && a.text !== 'N/A') : [];

                      return (
                        <div key={q.id} style={{
                          padding: '16px',
                          borderRadius: '10px',
                          background: 'rgba(0, 0, 0, 0.2)',
                          marginBottom: '16px',
                          border: '1px solid rgba(255, 255, 255, 0.05)'
                        }}>
                          <p style={{ fontSize: '0.95rem', marginBottom: '14px', lineHeight: 1.6 }}>{q.enunciado}</p>
                          
                          {hasMultipla && altsMultipla.length > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                              {altsMultipla.map(alt => {
                                const isSelected = resp?.resposta === alt.key;
                                const isCorrect = q.gabarito?.trim().toUpperCase() === alt.key;
                                let bg = 'rgba(0, 0, 0, 0.3)';
                                let bColor = 'rgba(255, 255, 255, 0.1)';

                                if (resp) {
                                  if (isSelected) {
                                    bg = isCorrect ? 'rgba(6, 240, 168, 0.2)' : 'rgba(239, 68, 68, 0.25)';
                                    bColor = isCorrect ? 'var(--cor-secundaria)' : '#ef4444';
                                  } else if (isCorrect) {
                                    bg = 'rgba(6, 240, 168, 0.15)';
                                    bColor = 'var(--cor-secundaria)';
                                  }
                                }

                                return (
                                  <button
                                    key={alt.key}
                                    disabled={!!resp}
                                    onClick={() => handleResponder(item.item_id, q, alt.key)}
                                    style={{
                                      display: 'flex',
                                      alignItems: 'flex-start',
                                      gap: '12px',
                                      padding: '12px 16px',
                                      borderRadius: '10px',
                                      border: `1px solid ${bColor}`,
                                      background: bg,
                                      color: '#ffffff',
                                      textAlign: 'left',
                                      fontSize: '0.9rem',
                                      lineHeight: 1.4,
                                      cursor: resp ? 'default' : 'pointer'
                                    }}
                                  >
                                    <span style={{
                                      width: '24px',
                                      height: '24px',
                                      borderRadius: '50%',
                                      background: isSelected ? 'var(--cor-primaria)' : 'rgba(255, 255, 255, 0.1)',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                      fontWeight: 800,
                                      fontSize: '0.8rem',
                                      flexShrink: 0
                                    }}>
                                      {alt.key}
                                    </span>
                                    <span style={{ flex: 1 }}>{alt.text}</span>
                                  </button>
                                );
                              })}
                            </div>
                          ) : (
                            <div style={{ display: 'flex', gap: '10px' }}>
                              {['C', 'E'].map(alt => (
                                <button
                                  key={alt}
                                  disabled={!!resp}
                                  onClick={() => handleResponder(item.item_id, q, alt)}
                                  style={{
                                    padding: '10px 20px',
                                    borderRadius: '8px',
                                    border: '1px solid rgba(255, 255, 255, 0.1)',
                                    background: resp?.resposta === alt 
                                      ? resp.acertou ? 'rgba(6, 240, 168, 0.25)' : 'rgba(239, 68, 68, 0.25)'
                                      : 'rgba(0, 0, 0, 0.3)',
                                    color: '#ffffff',
                                    fontWeight: 700,
                                    cursor: resp ? 'default' : 'pointer'
                                  }}
                                >
                                  {alt === 'C' ? 'Certo' : 'Errado'}
                                </button>
                              ))}
                            </div>
                          )}

                          {resp && (
                            <div style={{
                              marginTop: '12px',
                              fontSize: '0.85rem',
                              color: resp.acertou ? 'var(--cor-secundaria)' : '#f87171',
                              fontWeight: 600,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}>
                              {resp.acertou ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                              {resp.acertou ? 'Excelente! Revisão computada no AMV 2.0.' : `Incorreto. Gabarito: ${q.gabarito}. Agendado para repetição.`}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
