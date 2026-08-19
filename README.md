# ✈️ WoFF BHaH II Watchdog

[![CI](https://github.com/Malboro66/Woff_Mate/actions/workflows/ci.yml/badge.svg)](https://github.com/Malboro66/Woff_Mate/actions/workflows/ci.yml)

**WoFF BHaH II Watchdog** é uma aplicação companion em segundo plano para o simulador de voo *Wings over Flanders Fields: Between Heaven and Hell II* (WOFF BHaH II).

A aplicação monitoriza em tempo real as pastas de campanha do jogo, extrai dados de ficheiros de texto e binários ofuscados, e alimenta uma base de dados SQLite local. Além da extração de dados, o projeto introduz uma camada de RPG (Fadiga, Moral, Stress) e um gerador de Diário de Bordo narrativo, preparando o terreno para uma futura interface gráfica (WoFFBase UI).

---

## Compatibilidade e suporte

O WoFF Mate oferece suporte ao Windows 10 de 64 bits e ao Windows 11 de 64 bits, com Python da versão 3.10 até a 3.14. O suporte ao WOFF BH&H II limita-se aos formatos confirmados por amostras sanitizadas e testes de regressão; a versão exata do WoFF ainda não foi confirmada. A integração contínua valida Python 3.10 e 3.14 no Linux e executa uma validação básica com Python 3.10 no `windows-latest`.

- [Compatibilidade e relatórios seguros](docs/compatibility.md)
- [Migrações e recuperação da base de dados](docs/database-migrations.md)
- [Resolução de problemas](docs/troubleshooting.md)

Os guias contêm os limites e procedimentos completos; este resumo não os substitui.

---

## 🌟 Funcionalidades Principais

- **Monitorização em Tempo Real** — deteta automaticamente quando o jogo guarda progresso e processa os ficheiros sem interferir com o motor (Read-Only).
- **Engenharia Reversa de Ficheiros Binários** — decifra o `Pilot1Dossier.txt` e os ficheiros de esquadrões (Scratchpad), removendo a camada de ofuscação Hex e investigando a cifra interna (suspeita de ser XOR) implementada pela OBD Software.
- **Extração de Dados Pessoais** — nome real do piloto, data e local de nascimento, biografia gerada pelo jogo, ID da fotografia e membros do esquadrão (AI Wingmen) com patentes e biografias.
- **Plano de Voo e Mapa Tático** — lê o `mission.log` gerado pelo motor CFS3, extrai waypoints, converte coordenadas para Graus Decimais e regista a linha da frente de batalha.
- **Catálogo de Medalhas e Esquadrões** — no arranque, varre as pastas do jogo e cataloga todas as medalhas disponíveis e os parâmetros de todos os esquadrões.
- **Sistema RPG (Fase 2)** — calcula Fadiga, Moral e Stress do piloto com base no histórico de missões, ferimentos e tempo de voo.
- **Diário de Bordo Dinâmico** — gera entradas de texto imersivas para cada missão voada, baseadas no resultado, aeronave e vitórias obtidas.
- **Base de Dados SQLite Robusta** — transações atómicas e thread-safe para evitar corrupção de dados.

---

## 🔖 Versionamento

A versão da aplicação é declarada uma única vez em `woff/version.py`. O pacote
Python, a opção `woff-watchdog --version`, os metadados SQLite e
os metadados do executável PyInstaller obtêm a versão desse módulo. As versões
dos formatos de configuração e schema também vivem nesse módulo, mas evoluem
independentemente da versão da aplicação. Configurações sem esses campos (ou
com campos legados) continuam legíveis; configurações de formato futuro e bancos
com schema futuro são recusados antes de qualquer alteração. Bancos
antigos continuam a seguir o fluxo de backup e migração antes de serem reabertos.

Inventário consolidado na versão 3.2.0:

| Superfície | Versão | Origem atual |
|---|---:|---|
| Aplicação/pacote/CLI/build/executável/SQLite | 3.2.0 | `woff.version.__version__` |
| Schema SQLite | 3.1 | `woff.version.SCHEMA_VERSION` |
| Formato de configuração | 1 | `woff.version.CONFIG_VERSION` |
| Export schema em configurações antigas | 2.2 | aceite e migrado para 3.1 |

## ⚠️ Estado Atual do Projeto

O ciclo corretivo 3.2.1 foi concluído no código pela Issue
[#26](https://github.com/Malboro66/woff-mate/issues/26) e pela PR
[#33](https://github.com/Malboro66/woff-mate/pull/33). Esse registro não afirma
que uma release pública 3.2.1 tenha sido publicada.

O ciclo ativo é o **3.3.0: integridade e ingestão**, acompanhado pela Issue
[#50](https://github.com/Malboro66/woff-mate/issues/50). As Issues
[#34](https://github.com/Malboro66/woff-mate/issues/34) e
[#45](https://github.com/Malboro66/woff-mate/issues/45) já foram concluídas.
A prioridade imediata de integridade é a Issue
[#57](https://github.com/Malboro66/woff-mate/issues/57), seguida pela mudança de
scheduling da Issue [#36](https://github.com/Malboro66/woff-mate/issues/36).

O backlog operacional está no
[GitHub Project WoFF Mate Development](https://github.com/users/Malboro66/projects/1).
O Project organiza a execução. A `main`, o CI e os contratos versionados no
repositório permanecem como fontes técnicas.

Prioridades atuais:

1. preservar estatísticas autoritativas do Dossier durante merges de fontes parciais (#57)
2. concluir scheduling limitado, coalescido e com identidade canônica de paths (#36)
3. processar snapshots estáveis com retry transitório e limitado (#42)
4. tornar datas, ordenação e atualização de missões determinísticas (#40 e #39)
5. reprocessar ficheiros dependentes sem perda quando o Dossier ainda não está disponível (#27)

A investigação do Dossier continua relevante, mas não representa o único
bloqueador do projeto.

---

## 🏗 Arquitetura do Projeto

O WoFF Mate segue uma arquitetura de monólito modular. A aplicação permanece um
único programa Windows com um único banco SQLite, dividido nestes módulos
lógicos:

| Módulo | Responsabilidade |
|---|---|
| foundation | identidade do pacote e versões canônicas |
| domain | modelos, normalização, RPG e narrativas |
| persistence | SQLite, schema, transações e repositories |
| platform | configuração local e integração Windows |
| ingestion | decode, parsers, catálogos e observação de ficheiros |
| application | coordenação de campanha e watchdog |
| presentation | CLIs, relatórios, diagnóstico e editor |
| governance | validação dos contratos de engenharia |

Consulte:

- [arquitetura do monólito modular](docs/architecture/modular-monolith.md)
- [graph file executável](docs/architecture/project-graph.yaml)
- [catálogo de evals](docs/engineering/evals.md)
- [quality gates](docs/engineering/quality-gates.md)
- [autonomia progressiva](docs/engineering/autonomy.md)

> **Nota:** os dados reais e confiáveis do piloto vêm dos ficheiros `.txt` delimitados por `;` (via `pilot_data_parser.py`), não do XML. O `xml_parser.py` trata apenas de ficheiros de configuração do motor CFS3.
>
> O `config.json` é criado pela auto-deteção ou copiado localmente a partir de
> `config.example.json`; por conter caminhos próprios da instalação, permanece
> ignorado pelo Git.

---

## 📦 Instalação

### Pré-requisitos
- Python da versão 3.10 até a 3.14
- WoFF BHaH II instalado (a aplicação tenta detetar o caminho automaticamente via Registo do Windows)

### Passos

1. Clone o repositório e abra um terminal na sua raiz.
2. Crie um ambiente virtual:
```bash
   python -m venv .venv
```
3. Ative o ambiente virtual:
   - **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
   - **Windows (CMD):** `.venv\Scripts\activate.bat`
4. Instale o projeto e as dependências em modo editável:
```bash
   pip install -e .
```

Para desenvolvimento, instale o conjunto de dependências de teste e governança:

```bash
pip install -e ".[dev]"
```

---

## ⚙️ Configuração

Crie a configuração local a partir do modelo neutro incluído no repositório:

```bash
cp config.example.json config.json
```

No Windows PowerShell, use `Copy-Item config.example.json config.json`. Depois,
edite `watch_paths` e `export_path` com os caminhos da sua instalação. Se não
existir um `config.json`, o programa também tenta detetar o WoFF através do
Registo do Windows e cria o ficheiro quando a deteção é bem-sucedida.

O `config.json` contém caminhos próprios de cada instalação e não é versionado.
Também são locais e ignorados pelo Git os bancos SQLite, logs, ambientes
virtuais, caches, resultados de build e configurações do VS Code. Assim, instalar,
testar e executar um clone novo não adiciona esses artefactos ao repositório.

| Chave | Descrição |
|---|---|
| `watch_paths` | Pastas vigiadas pelo watchdog (normalmente `Pilots` e `Logs`) |
| `export_path` | Localização da base de dados SQLite (`woff_data.db`) |

### Atualização de versões anteriores

Em versões anteriores, o `config.json` era rastreado pelo Git. Se possui uma
configuração pessoal modificada, execute o procedimento abaixo no Windows
PowerShell, a partir da raiz do repositório:

```powershell
$repoRoot = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoRoot)) {
    throw "Execute este procedimento dentro do repositório."
}
$repoRoot = $repoRoot.Trim()
$configPath = Join-Path $repoRoot "config.json"
$backupDir = Join-Path (Split-Path -Parent $repoRoot) "Woff_Mate-backups"
$backup = Join-Path $backupDir ("config-{0}.json" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

# Guarde e confirme o backup fora do repositório.
New-Item -ItemType Directory -Force -Path $backupDir -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath $configPath -Destination $backup -ErrorAction Stop
if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
    throw "O backup de config.json não foi criado. Atualização cancelada."
}
$backupHash = (Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash
Write-Host "Backup confirmado em: $backup"

# Somente após confirmar o backup, limpe o índice e o ficheiro de trabalho e atualize.
git restore --staged --worktree -- config.json
if ($LASTEXITCODE -ne 0) { throw "Não foi possível restaurar config.json." }
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "git pull falhou; o backup permanece em $backup." }

# Reponha a configuração pessoal e valide o estado esperado.
Copy-Item -LiteralPath $backup -Destination $configPath -ErrorAction Stop
if ((Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash -ne $backupHash) {
    throw "A configuração pessoal restaurada não corresponde ao backup."
}
git check-ignore --quiet -- config.json
if ($LASTEXITCODE -ne 0) { throw "config.json não está ignorado pelo Git." }
git ls-files --error-unmatch -- config.example.json | Out-Null
if ($LASTEXITCODE -ne 0) { throw "config.example.json deixou de estar versionado." }

Write-Host "Configuração restaurada; config.json está ignorado e config.example.json está versionado."
```

O backup fica na pasta `Woff_Mate-backups`, ao lado da pasta do repositório e,
portanto, fora da sua árvore. Não o grave dentro do projeto: isso evita que
caminhos e outros dados pessoais sejam incluídos acidentalmente num commit.

---

## 🚀 Como Usar

Todos os comandos devem ser executados a partir da raiz do projeto.

### Modo Normal (Produção)
Inicia a monitorização em segundo plano. Corre até ser interrompido (`Ctrl+C`).
```bash
python -m woff.woff_watchdog
# Após instalar com `pip install -e .`:
woff-watchdog
```

### Modo Debug de Ficheiro Único
Testa a extração de um ficheiro específico e imprime os dados no terminal. Ideal para testar novos parsers sem abrir o jogo.
```bash
python -m woff.woff_watchdog --parse-file "C:\OBDSoftware\WOFF\OBDWW1 Over Flanders Fields\campaigns\CampaignData\Pilots\Pilot1Dossier.txt"
woff-watchdog --parse-file "C:\OBDSoftware\WOFF\OBDWW1 Over Flanders Fields\campaigns\CampaignData\Pilots\Pilot1Dossier.txt"
```

### Modo Descoberta
Regista em `woff_discovery.log` todos os ficheiros que o jogo gera, com um preview do conteúdo. Útil para mapear onde o jogo guarda novas informações.
```bash
python -m woff.woff_watchdog --discover
woff-watchdog --discover
```

### Ajuda
Mostra todas as opções disponíveis no CLI.
```bash
python -m woff.woff_watchdog --help
woff-watchdog --help
```

---

## 🎲 Sistema RPG e Diário de Bordo (Fase 2)

O Watchdog não se limita a ler ficheiros — ele interpreta-os. Sempre que uma missão termina e o `Pilot1Log.txt` é atualizado:

1. O `handler.py` insere a missão na base de dados.
2. O `CampaignEngine` é ativado em segundo plano.
3. Lê as últimas 10 missões do piloto na base de dados.
4. O `RPGSystem` calcula:
   - **Fadiga** — baseada em missões recentes (últimos 3 dias) e ferimentos.
   - **Moral** — baseada em vitórias, danos sofridos e estado atual do piloto.
   - **Stress** — baseado em contactos inimigos e aterragens forçadas.
5. O `NarrativeGenerator` cria um texto para o Diário de Bordo (ex: *"O céu de Flandres. Hoje voámos num Nieuport 10... O meu camarada Rene foi ferido."*).
6. Tudo é guardado nas tabelas `pilot_rpg_stats` e `diary_entries` da base de dados SQLite.

---

## 🗺 Roadmap do Projeto

| Ciclo | Estado | Escopo |
|---|---|---|
| 3.2.1 | concluído no código | #26, isolamento destrutivo do diário |
| 3.3.0 | ativo, tracker #50 | #34, #57, #45, #36, #42, #40, #39 e #27 |
| 3.4.0 | planejado | #41, #38, #35, #37, #44, #43 e #28 |
| 3.5.0 | planejado | #48, #47, #29, #46, #49 e #30 |

A futura interface permanece condicionada ao Portão A de dados confiáveis. Cada
ciclo exige critérios funcionais, evals, documentação e gates aplicáveis. CI
verde isoladamente não encerra um ciclo.

---

## 🛠 Tecnologias Utilizadas

- **Python 3.10–3.14**
- **Watchdog** — monitorização de eventos do sistema de ficheiros
- **SQLite3** — base de dados local embutida (sem servidor)
- **Dataclasses & Threading** — modelos de dados limpos e processamento assíncrono
- **xml.etree.ElementTree** — parsing de ficheiros de configuração do motor CFS3

---

## ⚖️ Aviso Legal

Este projeto é uma ferramenta de terceiros não oficial, criada para fins de análise pessoal e educacional. Não modifica ficheiros do jogo (funciona em modo Read-Only) e não está afiliado à OBD Software.