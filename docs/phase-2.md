# Fase 2 — Organizações, unidades e escopos

Implementada junto às Fases 3 e 4 com autorização do usuário.

- Plataforma: cadastro/edição/desativação dos metadados de organizações.
  Não concede leitura de recursos dos clientes.
- Organização: administrador edita somente a sua organização, cadastra e altera
  unidades com nome, identificador, endereço opcional, responsável, descrição,
  fuso IANA e estado. Contagem de câmeras vem do banco, com busca/filtro.
- Equipe: cadastro local de operador/supervisor, ativação/desativação,
  concessão de papel e escopo por unidade ou por toda a organização, revogação.
  Novo operador começa sem acesso a unidades.
- Isolamento: organização da sessão, filtros no backend, 404 para recursos de
  outro cliente ou sem escopo, FKs compostas no banco para relações entre clientes.
- Desativação: requer confirmação. Bloqueia acesso da organização ou reprodução
  das câmeras da unidade. Unidades não são removidas fisicamente nesta entrega.
- Migração: preserva usuários e unidades legadas; exige concessão explícita de
  acesso operacional aos operadores existentes.
- Provisionamento: comandos `setup-local` e `create-account`, sem senhas padrão.

Validação: testes de CRUD, fuso inválido, duplicidade, confirmação, IDs alterados
na URL e formulário, papéis, escopos, revogação, contas/unidades inativas,
relações no banco e preservação de dados. Fluxo também executado em navegador.
Consulte `validation.md` para evidências e `architecture.md` para a matriz.

Limites: sem convite por e-mail, recuperação de senha, MFA ou delegação de novos
administradores pela interface. PostgreSQL não foi executado; a validação de
produção é uma etapa separada. Cadastro local de equipe foi antecipado somente
para tornar os escopos funcionais. Administração e auditoria completas continuam
na Fase 11. As Fases 5 em diante aguardam autorização.
