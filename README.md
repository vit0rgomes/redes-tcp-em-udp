# 7 Análise Experimental de Resultados

Esta seção apresenta uma análise comparativa de três cenários experimentais que demonstram o comportamento do protocolo implementado sob diferentes condições de rede. Os experimentos foram conduzidos com 10.000 pacotes transmitidos em cada cenário.

## 7.1 Cenário 1: Com Controle de Congestionamento e Perdas (LOSS_RATE = 0.5%)

### 7.1.1 Configuração do Experimento

- Taxa de perda simulada: 0.5% (5 pacotes a cada 1000)
- CWND inicial: 1.0
- SSThresh inicial: 32
- CWND máximo: 77.2
- Timeout: 1.00 s
- Controle de congestionamento: Ativado

### 7.1.2 Resultados Obtidos

- Total enviado: 10.000 pacotes
- Retransmissões: 50 (0.50%)
- CWND final: 77.2 pacotes

### 7.1.3 Análise do Comportamento

O gráfico apresenta o padrão característico em dente de serra (vai subindo e descendo). O CWND inicia em 1.0, cresce exponencialmente durante Slow Start até SSThresh = 32.0, depois passa para crescimento linear na fase de Congestion Avoidance, atingindo picos de 77.2 pacotes. As quedas abruptas observadas (10-12 eventos) correspondem às perdas detectadas, onde o protocolo reduz CWND e entra em Fast Recovery.

## 7.2 Cenário 2: Com Controle de Congestionamento sem Perdas (LOSS_RATE = 0%)

### 7.2.1 Configuração do Experimento

- Taxa de perda simulada: 0% (rede ideal)
- CWND inicial: 1.0
- SSThresh inicial: 32.0
- CWND máximo: 100.0
- Timeout: 1.00 s
- Controle de congestionamento: Ativado

### 7.2.2 Resultados Obtidos

- Total enviado: 10.000 pacotes
- Retransmissões: 0 (0.00%)
- CWND final: 100.0 pacotes

### 7.2.3 Análise do Comportamento

O gráfico mostra crescimento suave e contínuo do CWND de 1.0 até 100.0 sem interrupções. A transição de Slow Start para Congestion Avoidance ocorre em CWND igual 32.0, com o protocolo atingindo 87.5% da capacidade máxima em aproximadamente 2 segundos. A ausência de retransmissões e eficiência de 100% confirmam operação ideal do protocolo em condições de rede sem perdas.

## 7.3 Cenário 3: Sem Controle de Congestionamento (CWND Fixo e com LOSS_RATE = 0.5%)

### 7.3.1 Configuração do Experimento

- Taxa de perda simulada: 0.5%
- CWND: 1.0 (fixo, sem crescimento)
- SSThresh: 2.0 (sem função prática)
- CWND máximo: 1.0
- Timeout: 1.00 s
- Controle de congestionamento: Desativado

### 7.3.2 Resultados Obtidos

- Total enviado: 10.000 pacotes
- Retransmissões: 48 (0.48%)
- CWND final: 1.0 pacote

### 7.3.3 Análise do Comportamento

O gráfico apresenta linha horizontal constante em CWND igual a 1.0 durante toda a transmissão de 250 segundos. Operando em modo stop-and-wait, o protocolo mostra degradação severa comparado ao Cenário 2, demonstrando subutilização da largura de banda. As 48 retransmissões observadas mesmo sem perdas configuradas indicam timeouts por RTT variável.
