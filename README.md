# TradingLab

Laboratório de pesquisa quantitativa para desenvolvimento, backtest, validação e forward testing de estratégias de trading.

O projeto foi desenvolvido inicialmente para estudar estratégias intraday no Nasdaq Futures utilizando dados de 1 minuto.

## Estrutura

### research/strategy
Regras de geração de sinais, incluindo:

- Opening Range Breakout (ORB)
- Fair Value Gap (FVG)
- versões experimentais dos detectores

### research/backtests
Motores de backtest utilizados durante o desenvolvimento das estratégias.

Inclui:

- Backtest V2
- Motor causal V3
- testes de diferentes relações risco/retorno
- pesquisa V5

### research/experiments
Experimentos realizados para estudar robustez e parâmetros.

Inclui:

- otimização de Risk/Reward
- análise de filtros
- sensibilidade do FVG
- Monte Carlo
- Block Bootstrap
- stress de custos
- comparação de modelos de stop

### research/validation
Auditorias e validações dos motores.

Inclui comparação entre diferentes implementações e validação causal dos sinais e execuções.

### research/forward
Ferramentas de Out-of-Sample e Forward Test.

Utilizadas para avaliar as estratégias após o período utilizado no desenvolvimento.

### data
Dados históricos, resultados de experimentos, auditorias e execuções de backtest.

Arquivos grandes CSV e Parquet são armazenados utilizando Git LFS.

## Estratégias pesquisadas

### V4

Estratégia baseada em:

- ORB: 09:30–09:45 America/New_York
- primeiro fechamento fora da ORB até 11:00
- confirmação por Fair Value Gap
- filtro operacional de FVG entre 6 e 12 pontos
- RR 1.25
- execução causal conservadora
- custos e slippage incluídos no backtest

### V5 Research

Pesquisa posterior avaliando diferentes modelos de stop e Risk/Reward.

Uma das configurações estudadas utiliza:

- stop Range 75%
- RR 1.50

A V5 permanece como pesquisa experimental.

## Metodologia

O processo de pesquisa utilizado no projeto segue aproximadamente:

Dados
-> geração de sinais
-> backtest causal
-> custos e slippage
-> análise por período
-> otimização
-> análise de sensibilidade
-> Monte Carlo
-> Walk-Forward
-> Out-of-Sample
-> Forward Test
-> auditoria

## Objetivo

O TradingLab não foi criado apenas para uma estratégia específica.

A estrutura pode ser reutilizada para pesquisar outras estratégias, como:

- ORB + VWAP
- VWAP Mean Reversion
- Previous Day High/Low
- Liquidity Sweep
- Breakout com volume
- estratégias baseadas em estrutura de mercado

## Aviso

Este projeto é destinado exclusivamente a pesquisa quantitativa e estudo de estratégias.

Resultados históricos e backtests não garantem resultados futuros.
