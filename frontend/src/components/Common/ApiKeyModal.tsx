import React, { useEffect, useState } from 'react';
import { useAI } from '../../context/AIContext';
import { Key, ShieldCheck, X } from 'lucide-react';

interface ApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ApiKeyModal: React.FC<ApiKeyModalProps> = ({ isOpen, onClose }) => {
  const { keys, setGroqKey, setGeminiKey } = useAI();
  const [tempGroq, setTempGroq] = useState(keys.groq);
  const [tempGemini, setTempGemini] = useState(keys.gemini);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      setTempGroq(keys.groq);
      setTempGemini(keys.gemini);
      setError('');
    }
  }, [isOpen, keys.groq, keys.gemini]);

  if (!isOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    const groqKey = tempGroq.trim();
    const geminiKey = tempGemini.trim();

    if (!groqKey && !geminiKey) {
      setError('Adicione sua chave Groq ou Gemini para liberar os recursos de IA.');
      return;
    }

    setGroqKey(groqKey);
    setGeminiKey(geminiKey);
    setError('');
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 1000);
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.7)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div className="glass-card" style={{
        width: '100%',
        maxWidth: '480px',
        padding: '28px',
        position: 'relative'
      }}>
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            background: 'none',
            border: 'none',
            color: 'var(--cor-texto-muted)',
            cursor: 'pointer'
          }}
        >
          <X size={20} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
          <div style={{
            padding: '8px',
            borderRadius: '8px',
            background: 'rgba(255, 140, 0, 0.15)',
            color: 'var(--cor-primaria)'
          }}>
            <Key size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', margin: 0 }}>Chaves de IA (BYOK)</h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--cor-texto-muted)' }}>
              Traga sua própria chave para diagnósticos e tutor
            </span>
          </div>
        </div>

        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {error && (
            <p role="alert" style={{ margin: 0, color: 'var(--cor-erro)', fontSize: '0.85rem' }}>
              {error}
            </p>
          )}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--cor-texto-muted)', marginBottom: '6px' }}>
              Groq API Key (Modelos rápidos)
            </label>
            <input
              type="password"
              value={tempGroq}
              onChange={e => setTempGroq(e.target.value)}
              placeholder="gsk_..."
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '8px',
                background: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid var(--border-color)',
                color: 'var(--cor-texto)',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
            <small style={{ display: 'block', marginTop: '4px', fontSize: '0.75rem' }}>
              <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer" style={{ color: 'var(--cor-secundaria)' }}>
                Obter chave no Console Groq ↗
              </a>
            </small>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--cor-texto-muted)', marginBottom: '6px' }}>
              Gemini API Key (Google AI)
            </label>
            <input
              type="password"
              value={tempGemini}
              onChange={e => setTempGemini(e.target.value)}
              placeholder="AIzaSy..."
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '8px',
                background: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid var(--border-color)',
                color: 'var(--cor-texto)',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
            <small style={{ display: 'block', marginTop: '4px', fontSize: '0.75rem' }}>
              <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" style={{ color: 'var(--cor-secundaria)' }}>
                Obter chave no Google AI Studio ↗
              </a>
            </small>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                border: '1px solid var(--border-color)',
                background: 'transparent',
                color: 'var(--cor-texto)',
                cursor: 'pointer',
                fontSize: '0.85rem'
              }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="btn-sovereign btn-primary"
              style={{ padding: '8px 16px', fontSize: '0.85rem' }}
            >
              {saved ? (
                <>
                  <ShieldCheck size={16} /> Salvo com Sucesso!
                </>
              ) : (
                'Salvar Configuração'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
