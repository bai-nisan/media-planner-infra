-- Test Vault Functionality from Supabase CLI
-- Run this with: supabase db connect < test_vault_cli.sql

-- Test 1: Check if vault schema exists
\echo '🔍 Checking vault schema...'
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'vault';

-- Test 2: Check vault functions availability
\echo '🛠️ Checking vault functions...'
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'vault' 
AND routine_name IN ('create_secret', 'update_secret', 'delete_secret');

-- Test 3: Create a test secret
\echo '🧪 Creating test secret...'
SELECT vault.create_secret(
    'test_credential_from_cli',
    'cli_test',
    'Test secret created from CLI'
) as secret_id;

-- Test 4: View secrets (metadata only)
\echo '📋 Listing vault secrets...'
SELECT id, name, description, created_at 
FROM vault.secrets 
WHERE name = 'cli_test'
ORDER BY created_at DESC;

-- Test 5: View decrypted secret (if you have permissions)
\echo '🔓 Testing decrypted view access...'
SELECT name, description, created_at
FROM vault.decrypted_secrets 
WHERE name = 'cli_test'
LIMIT 1;

-- Test 6: Clean up test secret
\echo '🧹 Cleaning up test secret...'
DELETE FROM vault.secrets WHERE name = 'cli_test';

\echo '✅ Vault CLI test completed!' 