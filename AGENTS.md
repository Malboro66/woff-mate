# AGENTS.md

## Projeto

WoFF_Mate é uma aplicação Python para Windows que processa dados do WoFF e mantém uma base SQLite persistente.

## Regras

- Preserve compatibilidade com Python 3.10.
- Antes de implementar qualquer issue, verifique issues fechadas, PRs e commits relacionados, inspecione o código afetado na `main` atual e reproduza o defeito com um teste ou procedimento determinístico. Se a `main` já satisfizer o comportamento esperado, interrompa a implementação e reclassifique a issue como candidata a duplicada, obsoleta ou já resolvida. Se uma correção anterior tiver sido parcial, limite a issue ao defeito restante e registre a referência histórica.
- Não altere dados de campanha sem backup.
- Toda mudança de schema exige teste de migração e reabertura.
- Não versione config.json, bancos, logs, builds ou dados pessoais.
- Não misture refatoração e nova funcionalidade na mesma PR.
- Use imports relativos dentro do pacote woff.
- Adicione testes de regressão para correções de bugs.
- Execute toda a suite antes de concluir.
- Não faça merge direto em main.

## Conclusão

A fase de implementação termina quando os critérios da issue foram atendidos, os testes passaram, o diff foi revisado e uma PR draft foi aberta.

A entrega integrada termina somente após os controles aplicáveis ao escopo — como revisão independente, CI, Codex Review e gates de governança — e uma decisão humana explícita de merge. A abertura da PR draft não conclui, por si só, a entrega integrada.

## Governança de escopo e proporcionalidade

- Consulte o [checkpoint integrado de 2026-10-18](docs/engineering/governance-checkpoint-2026-10-18.md) para distinguir estado atual, decisões, evidências históricas e restrições dos Product Gates. Revalide `main`, issues e PRs antes de tomar decisões.
- Não amplie critérios de aceite para campanhas de infraestrutura, plataformas secundárias, máquinas virtuais, testes especializados de acessibilidade, certificações ou revisões repetidas sem demonstrar que respondem a um requisito aprovado e modificam uma decisão concreta. Registre limitações ou evidência ausente e peça decisão do mantenedor para expansão material de custo ou escopo. Isso não dispensa gates aplicáveis.
- Spikes encerram quando há evidência suficiente para a decisão delimitada. Um review independente da PR não substitui um Full Application Review da `main` integrada.
- Nunca interprete CI verde, PR Draft, fixture/protótipo, suporte declarado pelo fornecedor ou toolkit ADR aceita como aprovação de Product Gates A–D, P1 com dados reais, launcher, RPG social ou release.
- Documentação/governança podem chegar até PR Draft sob L2; merge, mudanças de portão ou aceitação de risco permanecem decisões humanas.
