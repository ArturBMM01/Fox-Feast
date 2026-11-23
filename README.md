# Fox-Feast
Pygame - Projeto Final 

# Fox Feast — Banquete no Pântano 🦊

## Sobre o projeto

Fox Feast é um jogo de labirinto desenvolvido em Python, inspirado na mecânica de Pac-Man. O jogador controla uma raposa que precisa comer todos os pequenos jacarés do cenário enquanto foge de caçadores.

As frutas douradas ativam um poder temporário que permite à raposa comer os caçadores. O jogo possui pontuação, vidas, impulso de velocidade, animações, música, efeitos sonoros e três fases com cenários diferentes.

## Integrantes

- Henrique Campos de Paula Ribeiro
- Artur Belem Marchetti Moraes

## Fases

| Fase | Cenário | Tamanho do mapa | Caçadores |
|---|---|---|---|
| Fácil | Bosque das lanternas | 17 × 13 | 2 |
| Média | Margens do rio | 19 × 15 | 4 |
| Difícil | Ruínas do rio | 25 × 21 | 14 |

Na fase média, os caçadores começam distribuídos pelo mapa e afastados da posição inicial da raposa.

Para avançar, é necessário comer todos os pequenos jacarés e selecionar “Próxima fase”. Comer os caçadores e coletar todas as frutas não é obrigatório. Ao concluir a terceira fase, o jogador vence.

## Tecnologias utilizadas

- Python
- Pygame Community Edition (`pygame-ce`)

O Pygame é utilizado para criar a janela, desenhar os elementos, receber comandos do jogador, reproduzir áudio e controlar a atualização dos quadros.

Os desenhos e sons são gerados pelo próprio código, sem necessidade de baixar arquivos adicionais de imagens ou músicas.

## Instalação

É necessário ter o Python instalado.

Baixe ou clone o repositório e abra a pasta do projeto no VS Code. Se baixar um arquivo ZIP, extraia seu conteúdo antes de executar.

No terminal, dentro da pasta que contém `main.py` e `requirements.txt`, execute:

```bash
python -m pip install -r requirements.txt
```

O arquivo `requirements.txt` deve conter:

```text
pygame-ce==2.5.8
```

O pacote instalado se chama `pygame-ce`, mas é importado no código como `pygame`.

## Como executar

Depois de instalar a dependência, execute no terminal da pasta do projeto:

```bash
python main.py
```

Também é possível abrir `main.py` no VS Code e clicar em “Executar arquivo Python”, usando o mesmo interpretador em que a dependência foi instalada.

No Windows, se o comando `python` não for reconhecido, tente substituir `python` por `py` nos comandos de instalação e execução.

Os arquivos da pasta `foxfeast` precisam permanecer juntos e com seus nomes originais.

## Controles

| Tecla | Ação |
|---|---|
| Setas ou WASD | Mover a raposa |
| Espaço | Usar impulso de velocidade |
| P ou Esc | Pausar ou continuar a partida |
| N | Ligar ou desligar a música |
| M | Ligar ou desligar os efeitos sonoros |
| F11 | Alternar tela cheia |
| Enter | Selecionar uma opção do menu |

A música e os efeitos também podem ser controlados separadamente pelos botões da interface.

## Modos de dificuldade

| Característica | Explorador | Arcade |
|---|---|---|
| Vidas iniciais | 5 | 3 |
| Velocidade dos caçadores | 22% menor | Normal |
| Duração do poder da fruta | 9 segundos | 7 segundos |

A quantidade de caçadores de cada fase é a mesma nos dois modos.

## Pontuação e vidas

- Pequeno jacaré: 10 pontos.
- Fruta dourada: 50 pontos e ativação do poder temporário.
- Caçadores comidos durante o poder: 200, 400, 600 e até 800 pontos por caçador na sequência.
- Conclusão de fase: bônus de 500 pontos mais 100 por vida restante.
- Ao passar para outra fase, o jogador recupera uma vida, respeitando o limite do modo escolhido.

Sem o poder ativo ou proteção temporária, encostar em um caçador custa uma vida. A partida termina quando as vidas chegam a zero.

Os recordes e as preferências de áudio são salvos localmente.

## Organização do código

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Iniciar o jogo |
| `foxfeast/config.py` | Configurações gerais e modos de dificuldade |
| `foxfeast/levels.py` | Fases, labirintos e cálculo de caminhos |
| `foxfeast/entities.py` | Movimento e comportamento dos personagens |
| `foxfeast/world.py` | Regras, colisões, coleta e progressão |
| `foxfeast/art.py` | Desenhos, animações e partículas |
| `foxfeast/scenery.py` | Cenários e efeitos de ambiente |
| `foxfeast/audio.py` | Música e efeitos sonoros |
| `foxfeast/ui.py` | Menus, instruções, créditos e informações da partida |
| `foxfeast/storage.py` | Salvamento de recordes e preferências |
| `foxfeast/__init__.py` | Identificação do pacote |

## Vídeo de demonstração

https://youtu.be/RL0NqMy26x0?is=sZZ5wYmfVEBzrr8n


## Link da conversa com a Inteligência Artificial

https://chatgpt.com/share/e/6b044104-c4bc-83e8-80db-f6789498817b