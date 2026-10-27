# FlexoCost

Aplicativo Streamlit para controle de montagens, retrabalhos e indicadores. O app
pode ser executado localmente com SQLite ou publicado com PostgreSQL no Supabase.

## Executar localmente

1. Instale Python 3.11 ou superior.
2. Crie e ative um ambiente virtual.
3. Instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Copie `.streamlit/secrets.toml.example` para
   `.streamlit/secrets.toml` e substitua `APP_PASSWORD` por uma senha forte.
   Esse arquivo está ignorado pelo Git.
5. Inicie o aplicativo:

   ```powershell
   streamlit run app3.py
   ```

O SQLite local será criado como `totalflex.db` na pasta do projeto. Para usar o
PostgreSQL localmente, configure `DATABASE_URL` no arquivo de secrets e remova
`USE_SQLITE`.

## Publicar online

O GitHub armazena o código, o Supabase armazena os dados e o Streamlit Community
Cloud executa o aplicativo.

### 1. Enviar o código para o GitHub

Crie um repositório, de preferência privado, e envie os arquivos do projeto.
Confira que `.streamlit/secrets.toml` e `totalflex.db` não foram incluídos.
Com Git instalado, os comandos iniciais são:

```powershell
git init
git add .
git commit -m "Prepare FlexoCost for online deployment"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

### 2. Configurar o Supabase

1. Crie um projeto no Supabase e guarde a senha do banco em local seguro.
2. No painel do projeto, abra a opção de conexão ao banco e copie a URI
   PostgreSQL do pooler recomendada para aplicações hospedadas. Use a senha do
   banco, codificando caracteres especiais conforme instruído pelo Supabase.
3. O aplicativo cria as tabelas `montagens` e `observacoes_melhoria` na primeira
   inicialização. Não é necessário habilitar a API REST nem colocar uma chave
   `anon` ou `service_role` no aplicativo.

### 3. Publicar no Streamlit Community Cloud

1. Crie um app no Streamlit Community Cloud conectado ao repositório GitHub.
2. Selecione `app3.py` como arquivo principal.
3. Nas configurações avançadas, escolha Python 3.11 e adicione os secrets abaixo,
   substituindo os valores pelos seus:

   ```toml
   DATABASE_URL = "postgresql://..."
   APP_PASSWORD = "uma-senha-forte-e-diferente-da-senha-do-banco"
   ```

4. Publique ou reinicie o app. O status exibido no cabeçalho deve indicar
   **Online**.

Nunca publique `DATABASE_URL`, `APP_PASSWORD` ou a senha do banco em arquivos
versionados, mensagens, capturas de tela ou código. Cadastre-os somente nos
secrets do serviço que executa o aplicativo.

## Acesso e dados

- O app exige uma senha compartilhada configurada em `APP_PASSWORD`; os
  visitantes não autenticados não conseguem acessar os dados. Todas as pessoas
  que compartilham essa senha veem os mesmos registros.
- Não use este modo se precisar de contas individuais, permissões por usuário ou
  trilha de auditoria por pessoa; isso requer autenticação/autorização
  individual.
- O arquivo `totalflex.db` local não é enviado nem migrado. A implantação inicia
  com tabelas vazias no Supabase.
- O banco local e o arquivo de estado do período de teste são ignorados pelo
  Git. O armazenamento de arquivos do Streamlit Community Cloud é efêmero; o
  PostgreSQL do Supabase é o armazenamento persistente.
