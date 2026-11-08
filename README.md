# Portfólio · Cassia Cristina

Site: **https://cassiacristina0o.github.io/**

Portfólio de automação e integração em Python. É uma página única, em HTML e CSS, que se adapta sozinha ao celular e ao computador. O JavaScript fica restrito ao formulário de contato e à demonstração do ETL (stlite).

## O que tem no site

- **Projetos:** [Zm-bot](https://github.com/CassiaCristina0o/Zm-bot-), [Upstreamer](https://github.com/CassiaCristina0o/upstreamer) e [análise do cartão corporativo](https://github.com/CassiaCristina0o/analise-cartao-corporativo).
- **Veja funcionando:** o ETL do cartão corporativo rodando no navegador e a [notícia do dia](https://github.com/CassiaCristina0o/noticias-diaria), publicada todo dia às 8h, escolhida na véspera por uma tarefa agendada.
- **Contato:** um formulário (nome, e-mail e o que você precisa) que chega no meu e-mail, e também GitHub, LinkedIn, Discord e X, com um QR code que abre este site.

## Arquivos

| Arquivo | O que é |
| --- | --- |
| `index.html` | A página inteira, com o CSS dentro |
| `qrcode.svg` | QR code que aponta para o endereço do site |
| `avatar.jpg`, `fundo.jpg` | Imagens da página |
| `demo-etl/` | A demonstração do ETL que aparece no quadro do site |

## Demonstração do ETL

Roda inteira no navegador, sem servidor, com [stlite](https://github.com/whitphx/stlite) (Streamlit e Python no navegador). Usa uma amostra de três meses (junho a agosto de 2026) do cartão corporativo do governo federal, dados públicos do Portal da Transparência. Nome, CPF e favorecido estão ocultos, por privacidade (LGPD).

O código completo do projeto está em [analise-cartao-corporativo](https://github.com/CassiaCristina0o/analise-cartao-corporativo).
