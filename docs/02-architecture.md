# 02 — Arquitetura

## Estilo arquitetural
Arquitetura modular monolítica com apps Django separados por domínio.

## Princípios
- separar domínio da aplicação e integração com OTServ;
- encapsular diferenças de schema por versão;
- manter o sistema de temas desacoplado;
- permitir evolução gradual.

## Camadas
- Presentation
- Application
- Domain
- Infrastructure
