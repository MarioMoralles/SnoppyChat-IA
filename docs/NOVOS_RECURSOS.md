# 🚀 Novos Recursos do Snoopy

## 1. ⚡ Wake Word — Velocidade e Precisão
Antes: transcrevia TODO áudio de 15s com Whisper (lento, errava o nome).
Agora: detector dedicado (openWakeWord) escuta só a ativação. Whisper só roda DEPOIS.
```bash
pip install openwakeword
```
⚠️ Modelo base detecta "hey jarvis". Para "Snoopy" real, treine em https://github.com/dscripka/openWakeWord e configure "wake_word_modelo_caminho".

## 2. 🎨 Geração de Imagens Offline
Stable Diffusion local via diffusers.
```bash
pip install diffusers torch transformers accelerate
```
Diga: "Snoopy, gere uma imagem de um cachorro astronauta" → salva em Pictures/Snoopy_Imagens.
Melhor com GPU NVIDIA. Em CPU é lento (roda em segundo plano).

## 3. 🔧 Controle da Máquina
Criar/organizar pastas, abrir apps e sites, pesquisar no Google, gerar relatórios, info do sistema.
Ex: "Snoopy, organize minha pasta de downloads"
⚠️ Pesquisa web precisa de internet.

## 4. 🖥️ Interface Gráfica
```bash
pip install fastapi uvicorn[standard] python-multipart
python main.py --modo interface
```
Abra http://localhost:8000 — botão de falar, texto e voz no navegador.

## 5. 🧠 Memória Inteligente
Busca semântica: pip install sentence-transformers
Obsidian: configure "obsidian_vault" com o caminho do seu vault.

## 6. 💡 Conversa Proativa
Ativada por padrão. Oferece sugestões úteis quando faz sentido.

## Nota honesta sobre "ficar mais inteligente"
O modelo Llama NÃO se retreina com uso. O que melhora é a memória/contexto: quanto mais o Snoopy sabe de você (embeddings + Obsidian), mais personalizadas as respostas. Efeito prático = parece aprender; mecanismo = acumular conhecimento.
