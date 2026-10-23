# MSS + FVG Research

Pesquisa quantitativa de uma estratégia baseada em:

- Market Structure Shift (MSS)
- Fair Value Gap (FVG)
- Order Block aproximado
- entradas limitadas dentro do FVG
- saídas parciais em múltiplos de R
- break-even após a primeira parcial

## Baseline

O baseline reproduz os parâmetros padrão do Pine Script original.

### Estrutura

- Pivot: 5 barras
- Validade do setup: 20 barras

### Entrada

- Entrada: 50% do FVG
- Stop buffer: 0 pontos
- Stop máximo: 50 pontos

### Setups

- Reversão: habilitada
- Continuação: habilitada
- Long: habilitado
- Short: habilitado
- Intervalo mínimo: 60 minutos

### Sessão

09:30–16:00 America/New_York.

### Gestão

3 contratos:

- Contrato 1: 1R
- Contrato 2: 2R
- Contrato 3: 3R

Após a primeira parcial, o stop restante é movido para break-even.

## Processo de pesquisa

1. Baseline sem otimização
2. Validação causal
3. Reversão vs continuação
4. Long vs short
5. Análise de horários
6. Análise do tamanho do FVG
7. Entrada dentro do FVG
8. Modelos de stop
9. Modelos de saída
10. Sensibilidade de parâmetros
11. Monte Carlo
12. Walk-forward
13. Out-of-sample
14. Forward test
15. Congelamento da estratégia

Nenhuma alteração de parâmetros deve ser considerada melhoria apenas por aumentar o lucro histórico. A seleção deve considerar robustez e estabilidade fora da amostra.