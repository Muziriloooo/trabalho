# Vídeo sintético de demonstração

`demo.mp4` é um padrão geométrico gerado por FFmpeg (`testsrc2`) a 640 × 360,
12 fps, 12 segundos, H.264/YUV420p, sem áudio, pessoas ou imagens de terceiros.
Contém a identificação “SENTINELA AI — VIDEO SINTETICO”.

O arquivo gerado nesta entrega é disponibilizado sob CC0-1.0. Pode ser usado
na demonstração comercial sem imagens de pessoas ou dependência de hardware.
O FFmpeg é uma ferramenta de geração opcional, não é distribuído com o projeto.
Para recriar o arquivo, use `scripts/generate-demo.sh` com FFmpeg instalado.

O vídeo fica fora de `static/`. A aplicação o serve somente por uma câmera de
demonstração ativa, numa unidade ativa, depois de autenticar e conferir o escopo
da organização e da unidade. Não existe rota pública de mídia.
