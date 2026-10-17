# Plano da Fase 2 — depende de aprovação

Nenhum CRUD desta fase foi implementado.

1. **Papéis e escopos.** Definir a matriz de leitura/escrita de organizações e
   unidades; evoluir para RoleAssignment com escopo de unidade e concessor.
   Manter o superadministrador sem acesso automático a dados de clientes.
2. **Banco e migrações.** Evoluir Organization com identificador e responsável;
   Site com identificador único por organização, endereço comercial opcional,
   responsável, status e timezone IANA validado. Criar constraints, índices e
   migrações preservando usuários existentes. Validar upgrade e rollback em base
   temporária; validar PostgreSQL antes de adotá-lo em operação.
3. **Escopo obrigatório no backend.** Resolver a organização pela sessão.
   Consultas e alterações sempre recebem esse escopo. Não aceitar
   organization_id arbitrário do formulário. Recursos de outro cliente retornam
   404, sem confirmar sua existência. Papel ou unidade insuficiente retorna 403.
4. **Fluxos funcionais.** Criar telas de listagem, pesquisa, cadastro, edição e
   desativação com validação, CSRF, mensagens claras, estados vazios e confirmação
   das ações. Organização e unidade inativas impedem novas operações conforme
   a política definida. Adiar remoção definitiva enquanto houver dependências.
5. **Dados demonstrativos.** Separar a opção de demonstração dos cadastros reais.
   Ainda sem câmeras cadastráveis: contagem real por unidade deve ser zero, com
   indicação explícita de que o inventário será implementado na Fase 3.
6. **Testes.** Criar duas organizações com administradores, supervisores,
   operadores e unidades distintas. Verificar isolamento em GET/POST, alteração
   de IDs na URL e no corpo, concessão de escopo, revogação, entradas inválidas,
   duplicidade, timezone, organização inativa, CSRF e escape de conteúdo.
   Verificar persistência após reinício e integridade das relações.
7. **Aceitação.** Demonstrar os fluxos com dados locais; executar suíte completa;
   confirmar ausência de acesso cruzado, documentar a matriz e limites; atualizar
   README e migrações. Aguardar nova aprovação antes da Fase 3.

Fora da Fase 2: câmeras reais, streaming, análise de vídeo, biometria, cobranças,
acionamento de hardware e disponibilização comercial.
