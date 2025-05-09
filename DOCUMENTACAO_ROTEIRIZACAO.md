# Documentação Detalhada das Funções de Roteirização Wazelog

Este documento descreve as principais funções e etapas do fluxo de roteirização do sistema Wazelog, detalhando o papel de cada função e módulo envolvido.

---

## 1. Pré-processamento e Agrupamento Inicial

### clusterizar_pedidos (routing/utils.py)
- **O que faz:** Agrupa pedidos em clusters iniciais para roteirização, considerando regiões e/ou proximidade geográfica.
- **Como funciona:**
  - Se a coluna 'Região' existir e for informativa, cada região vira um cluster.
  - Se houver mais regiões do que clusters (veículos), regiões pequenas são agrupadas por proximidade usando KMeans nos centroides das regiões.
  - Se não houver regiões, aplica KMeans diretamente nas coordenadas (Latitude, Longitude).
  - Pedidos sem coordenada ficam com cluster -1.
  - O número de clusters é definido pelo número de veículos ou conforme necessidade do cenário.
  - Retorna um array de rótulos alinhado ao DataFrame original.

---

## 2. Cálculo de Matrizes de Distância

### calcular_matriz_distancias (routing/distancias.py)
- **O que faz:** Calcula a matriz de distâncias entre todos os pedidos e o depósito, usando OSRM local ou API externa.
- **Como funciona:**
  - Recebe DataFrame de pedidos e coordenadas do depósito.
  - Retorna matriz numpy de distâncias (em metros ou minutos).

---

## 3. Solvers de Roteirização (CVRP)

### solver_cvrp (routing/cvrp.py e routing/cvrp_flex.py)
- **O que faz:** Resolve o problema de roteirização de veículos com capacidade (CVRP), alocando pedidos em rotas otimizadas para cada veículo.
- **Como funciona:**
  - Recebe pedidos, frota, matriz de distâncias e parâmetros.
  - Usa Google OR-Tools para criar o modelo de roteirização.
  - Define callbacks de distância e demanda (peso/volume).
  - Respeita capacidade dos veículos, janelas de tempo e restrições de rodízio.
  - Retorna DataFrame com rotas, sequência de entregas, veículo alocado, carga, distância etc.

### solver_cvrp_por_cluster (routing/cvrp.py)
- **O que faz:** Executa o solver CVRP separadamente para cada cluster/região.
- **Como funciona:**
  - Para cada cluster, roda o solver considerando apenas os pedidos daquele grupo e os veículos disponíveis.
  - Junta os resultados em um único DataFrame de rotas.

---

## 4. Pós-processamento e Balanceamento

### priorizar_regioes_preferidas (routing/pos_processamento.py)
- **O que faz:** Realoca pedidos para veículos que têm preferência por determinadas regiões (restrição suave).
- **Como funciona:**
  - Após a roteirização, verifica se há pedidos em regiões preferidas de cada veículo.
  - Move pedidos para veículos preferenciais, se possível, sem violar capacidade.
  - Retorna DataFrame de rotas ajustado e o número de realocações.

### balanceamento_visual_placeholder (routing/pos_processamento.py)
- **O que faz:** Placeholder para futura interface de balanceamento manual/interativo das rotas.

---

## 5. Utilitários e Validações

### placa_em_rodizio_sp, pedido_destino_sp (routing/utils.py)
- **O que fazem:**
  - `placa_em_rodizio_sp`: Verifica se uma placa está em rodízio em SP para determinado dia.
  - `pedido_destino_sp`: Verifica se o destino do pedido é o município de São Paulo/SP.

### validar_dataframe (routing/utils.py)
- **O que faz:** Valida se um DataFrame possui as colunas obrigatórias e não está vazio.

---

## 6. Aprendizado de Máquina (Opcional)

### sugerir_agrupamento_ml (routing/pos_processamento.py)
- **O que faz:** Sugere agrupamento de pedidos usando modelo de ML treinado (placeholder, não obrigatório).

---

## 7. Fluxo Geral da Roteirização

1. **Importação dos pedidos e frota**
2. **Clusterização inicial dos pedidos** (por região ou KMeans)
3. **Cálculo da matriz de distâncias**
4. **Execução do solver CVRP** (por cluster ou global)
5. **Pós-processamento:**
   - Prioriza regiões preferidas
   - Balanceia peso/capacidade
   - Ajusta para rodízio de placas (SP)
6. **Geração do DataFrame final de rotas**
7. **Visualização e exportação dos resultados**

---

Para detalhes de cada função, consulte os arquivos em `routing/`.
