export interface AIResponse {
  content: string;
  error?: string;
}

const readApiError = async (res: Response, provider: string) => {
  try {
    const body = await res.json();
    return body.error?.message || `Erro ${provider} HTTP ${res.status}`;
  } catch {
    return `Erro ${provider} HTTP ${res.status}`;
  }
};

const getGroqModel = async (apiKey: string): Promise<string> => {
  const res = await fetch('https://api.groq.com/openai/v1/models', {
    headers: { Authorization: `Bearer ${apiKey}` }
  });

  if (!res.ok) {
    throw new Error(await readApiError(res, 'Groq'));
  }

  const data = await res.json();
  const models = (data.data || []).map((model: { id: string }) => model.id);
  const preferred = [
    'llama-3.3-70b-versatile',
    'llama-3.1-8b-instant',
    'openai/gpt-oss-20b',
    'openai/gpt-oss-120b'
  ];
  const model = preferred.find(candidate => models.includes(candidate)) || models.find((id: string) => /llama|gpt/i.test(id));

  if (!model) {
    throw new Error('Sua chave Groq foi aceita, mas não há um modelo de chat disponível para ela.');
  }

  return model;
};

export const callGroq = async (apiKey: string, prompt: string, systemPrompt?: string): Promise<AIResponse> => {
  try {
    const model = await getGroqModel(apiKey);
    const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model,
        messages: [
          ...(systemPrompt ? [{ role: 'system', content: systemPrompt }] : []),
          { role: 'user', content: prompt }
        ],
        temperature: 0.2
      })
    });

    if (!res.ok) {
      return { content: '', error: await readApiError(res, 'Groq') };
    }

    const data = await res.json();
    return { content: data.choices?.[0]?.message?.content || '' };
  } catch (err: any) {
    return { content: '', error: err.message || 'Falha na conexão com a API Groq' };
  }
};

export const callGemini = async (apiKey: string, prompt: string, systemPrompt?: string): Promise<AIResponse> => {
  try {
    const modelsRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`);
    if (!modelsRes.ok) {
      throw new Error(await readApiError(modelsRes, 'Gemini'));
    }

    const modelsData = await modelsRes.json();
    const models = (modelsData.models || []).filter((model: { supportedGenerationMethods?: string[] }) =>
      model.supportedGenerationMethods?.includes('generateContent')
    );
    const preferred = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'];
    const selectedModel = preferred
      .map(name => `models/${name}`)
      .find(name => models.some((model: { name: string }) => model.name === name)) || models[0]?.name;

    if (!selectedModel) {
      throw new Error('Sua chave Gemini foi aceita, mas não há um modelo compatível com generateContent.');
    }

    const url = `https://generativelanguage.googleapis.com/v1beta/${selectedModel}:generateContent?key=${apiKey}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [
          ...(systemPrompt ? [{ role: 'user', parts: [{ text: `[INSTRUÇÃO DO SISTEMA]: ${systemPrompt}` }] }] : []),
          { role: 'user', parts: [{ text: prompt }] }
        ]
      })
    });

    if (!res.ok) {
      return { content: '', error: await readApiError(res, 'Gemini') };
    }

    const data = await res.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
    return { content: text };
  } catch (err: any) {
    return { content: '', error: err.message || 'Falha na conexão com a API Gemini' };
  }
};

export const generateAIAnswer = async (
  keys: { groq?: string; gemini?: string },
  prompt: string,
  systemPrompt?: string
): Promise<AIResponse> => {
  const groqKey = keys.groq?.trim();
  const geminiKey = keys.gemini?.trim();
  const providerErrors: string[] = [];

  if (!groqKey && !geminiKey) {
    return {
      content: '',
      error: 'Nenhuma chave de IA válida configurada. Abra “Configurar IA” e adicione sua própria chave Groq ou Gemini.'
    };
  }

  if (groqKey) {
    const r = await callGroq(groqKey, prompt, systemPrompt);
    if (!r.error) return r;
    providerErrors.push(`Groq: ${r.error}`);
  }

  if (geminiKey) {
    const r = await callGemini(geminiKey, prompt, systemPrompt);
    if (!r.error) return r;
    providerErrors.push(`Gemini: ${r.error}`);
  }

  return {
    content: '',
    error: `A IA não conseguiu gerar a resposta. Motivo: ${providerErrors.join(' ')} Solução: confirme se a chave está ativa, com acesso ao modelo listado pelo provedor, e tente novamente em “Configurar IA”.`
  };
};
