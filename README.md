# 🐾 Snoopy — Assistente Pessoal de IA 100% Local

> Seu assistente pessoal inteligente que roda **completamente offline** no seu computador.  
> Sem assinaturas. Sem nuvem. Sem coleta de dados. Seus dados ficam **só com você**.

---

## ✨ O que é o Snoopy?

O Snoopy é um assistente de voz e texto baseado em IA que processa tudo localmente na sua máquina. Você fala (ou digita), ele entende, responde, e pode executar tarefas complexas **em segundo plano** enquanto você continua seu trabalho.

```
Você: "Snoopy, cria um script Python para organizar meus downloads por tipo de arquivo"
Snoopy: "Certo! Vou processar isso em segundo plano. Tarefa #1 iniciada."
... [alguns minutos depois] ...
Snoopy: "Tarefa #1 concluída! Aqui está o script Python que você pediu: ..."
```

---

## 🚀 Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| 🎙️ **Reconhecimento de Voz** | Whisper offline — alta precisão em português |
| 🔊 **Síntese de Voz** | Piper TTS ou pyttsx3 — resposta em voz natural |
| 🧠 **Memória Persistente** | Lembra de conversas e aprende suas preferências |
| ⚙️ **Tarefas em Background** | Processa tarefas pesadas enquanto você trabalha |
| 🤖 **LLM Local** | Llama 3, Mistral, Phi-3 via Ollama ou LM Studio |
| 💬 **Modo Texto** | Funciona no terminal sem microfone |
| 🔒 **100% Privado** | Nenhum dado sai do seu computador |

---

## 📋 Pré-requisitos

### 1. Python 3.10+
```bash
python --version   # Deve ser 3.10 ou superior
```

### 2. Ollama (recomendado para o LLM)
```bash
# Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# Windows: baixe o instalador em https://ollama.com/download
```

Após instalar, baixe um modelo (escolha conforme sua RAM):
```bash
# Leve (4GB RAM) — recomendado para começar
ollama pull llama3.2:3b

# Médio (8GB RAM) — melhor qualidade
ollama pull llama3.1:8b

# Avançado (16GB RAM)
ollama pull mistral:7b
```

### 3. (Opcional) Piper TTS — voz neural de alta qualidade
```bash
# Linux/macOS: baixe o binário em https://github.com/rhasspy/piper/releases
# Coloque o executável 'piper' em algum lugar no seu PATH

# Depois, baixe a voz em português:
python scripts/baixar_voz_piper.py --voz pt_BR-faber-medium
```

---

## ⚡ Instalação Rápida

```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/snoopy.git
cd snoopy

# 2. Crie um ambiente virtual (recomendado)
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure o Snoopy
python main.py --configurar

# 5. Inicie!
python main.py
```

---

## 🎮 Modos de Uso

### Modo Voz (padrão)
```bash
python main.py
# Diga "Snoopy" + seu comando
# Exemplos:
# "Snoopy, que horas são?"
# "Snoopy, escreve um email de agradecimento para meu cliente"
# "Snoopy, cria um script para renomear arquivos em lote"
```

### Modo Texto (sem microfone)
```bash
python main.py --modo texto
# Digite normalmente no terminal
```

### Modo Silencioso (sem resposta por voz)
```bash
python main.py --sem-voz
```

### Configuração
```bash
python main.py --configurar
```

---

## 🗂️ Estrutura do Projeto

```
snoopy/
├── main.py                         # Ponto de entrada principal
├── requirements.txt                # Dependências Python
├── .env.exemplo                    # Template de variáveis de ambiente
│
├── snoopy/                         # Código-fonte principal
│   ├── nucleo.py                   # Orquestrador — conecta todos os módulos
│   │
│   ├── voz/                        # 🎙️ Módulo de Voz
│   │   ├── ouvinte.py              # Captura e transcrição (Whisper offline)
│   │   └── sintetizador.py         # Síntese de voz (Piper / pyttsx3)
│   │
│   ├── ia/                         # 🤖 Módulo de IA
│   │   ├── processador.py          # Comunicação com Ollama/LM Studio
│   │   └── intencao.py             # Detecta intenção (background vs imediato)
│   │
│   ├── automacao/                  # ⚙️ Módulo de Automação
│   │   └── gerenciador_tarefas.py  # Execução de tarefas em segundo plano
│   │
│   ├── memoria/                    # 🧠 Módulo de Memória
│   │   └── gerenciador_memoria.py  # Memória persistente com SQLite
│   │
│   └── utils/                      # 🔧 Utilitários
│       ├── config.py               # Gerenciamento de configuração
│       ├── logger.py               # Sistema de logging
│       └── configurador.py         # Assistente de configuração interativo
│
├── scripts/
│   └── baixar_voz_piper.py         # Baixa vozes Piper para uso offline
│
├── tests/
│   └── test_snoopy.py              # Testes automatizados
│
├── config/                         # Exemplos de configuração
└── docs/                           # Documentação adicional
```

---

## ⚙️ Configuração Detalhada

O arquivo de configuração fica em `~/.config/snoopy/config.json`:

```json
{
  "ia_backend": "ollama",
  "ia_modelo": "llama3.2:3b",
  "ia_url_base": "http://localhost:11434",
  "ia_temperatura": 0.7,
  "ia_max_tokens": 512,

  "whisper_modelo": "base",
  "whisper_idioma": "pt",

  "tts_motor": "piper",
  "tts_voz_piper": "pt_BR-faber-medium",

  "audio_limiar_silencio": 0.01,
  "audio_duracao_silencio_seg": 1.5
}
```

### Modelos de LLM recomendados

| Modelo | RAM necessária | Qualidade | Velocidade |
|---|---|---|---|
| `llama3.2:3b` | 4GB | Boa | ⚡⚡⚡ |
| `llama3.1:8b` | 8GB | Muito boa | ⚡⚡ |
| `mistral:7b` | 8GB | Muito boa | ⚡⚡ |
| `phi3:mini` | 4GB | Boa | ⚡⚡⚡ |
| `llama3.1:70b` | 48GB+ | Excelente | ⚡ |

### Modelos Whisper

| Modelo | Tamanho | Velocidade | Precisão |
|---|---|---|---|
| `tiny` | 75MB | ⚡⚡⚡⚡ | Baixa |
| `base` | 150MB | ⚡⚡⚡ | Boa ← recomendado |
| `small` | 490MB | ⚡⚡ | Muito boa |
| `medium` | 1.5GB | ⚡ | Excelente |

---

## 🔒 Privacidade

- **Processamento 100% local** — nenhum dado enviado para servidores externos
- **Memória em SQLite local** — armazenada em `~/.local/share/snoopy/`
- **Logs locais** — em `~/.local/share/snoopy/logs/`
- **Sem telemetria** — zero coleta de dados

---

## 🧪 Testes

```bash
# Instala dependências de teste
pip install pytest pytest-asyncio

# Executa os testes
python -m pytest tests/ -v
```

---

## 🛠️ Solução de Problemas

### "Backend de IA não disponível"
```bash
# Verifique se o Ollama está rodando
ollama serve
# ou
ollama list   # lista modelos instalados
```

### "Nenhum modelo Whisper encontrado"
```bash
pip install faster-whisper
# ou
pip install openai-whisper
```

### "sounddevice: erro ao abrir microfone"
```bash
# Linux: instale as libs de áudio
sudo apt install portaudio19-dev python3-pyaudio
pip install sounddevice --force-reinstall
```

### Sem voz no Linux
```bash
sudo apt install alsa-utils
# Teste: aplay -l  (lista dispositivos)
```

---

## 📄 Licença

- **Uso pessoal**: Gratuito e livre
- **Uso comercial**: Consulte os termos no arquivo LICENSE

---

## 🤝 Contribuições

Issues e Pull Requests são bem-vindos!  
O projeto é desenvolvido de forma aberta e em português.

---

*Snoopy — seu assistente, sua máquina, suas regras.* 🐾
