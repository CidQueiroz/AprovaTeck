import { afterEach, describe, it, expect, vi } from 'vitest';
import { generateAIAnswer } from '../services/aiService';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('🤖 Tutor IA & Geração de Conteúdo (aiService)', () => {
  it('deve retornar aviso amigável quando chaves de API não forem informadas', async () => {
    const keysEmpty = { groq: '', gemini: '' };
    const resposta = await generateAIAnswer(keysEmpty, 'Explique o que é RPD.');
    
    expect(resposta.error).toContain('Nenhuma chave de IA válida configurada');
  });

  it('deve possuir chave de bancas prioritárias padrão', () => {
    const bancasPadrao = ['FGV', 'CEBRASPE', 'CESGRANRIO', 'FCC', 'IBFC', 'VUNESP'];
    expect(bancasPadrao).toContain('FGV');
    expect(bancasPadrao).toContain('CEBRASPE');
  });

  it('deve informar o motivo e a solução quando o modelo falhar', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: [{ id: 'llama-3.1-8b-instant' }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { message: 'modelo indisponível' } }), { status: 404 }));

    const resposta = await generateAIAnswer({ groq: 'chave-de-teste' }, 'Gere uma questão.');

    expect(resposta.error).toContain('modelo indisponível');
    expect(resposta.error).toContain('Solução:');
  });
});
