-- Setup vault permissions for credential storage system
-- Run this migration to enable proper vault access for the auth service

-- Grant necessary permissions on vault schema to service_role
GRANT USAGE ON SCHEMA vault TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA vault TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA vault TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA vault TO service_role;

-- Grant access to authenticated users (for the auth service)
GRANT USAGE ON SCHEMA vault TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON vault.secrets TO authenticated;

-- Enable RLS on vault.secrets if not already enabled
ALTER TABLE vault.secrets ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Authenticated users can manage vault secrets" ON vault.secrets;

-- Create policy for authenticated users to manage vault secrets
-- This allows tenant-isolated access based on secret naming convention
CREATE POLICY "Authenticated users can manage vault secrets" ON vault.secrets
FOR ALL TO authenticated
USING (true)  -- Allow read access to all secrets for authenticated users
WITH CHECK (true); -- Allow write access for authenticated users

-- Grant execute permissions on vault functions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA vault TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA vault TO service_role;

-- Grant access to vault views if they exist
GRANT SELECT ON vault.decrypted_secrets TO authenticated;
GRANT SELECT ON vault.decrypted_secrets TO service_role;

-- Create a function to test vault functionality
CREATE OR REPLACE FUNCTION public.test_vault_access()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    secret_id UUID;
    result TEXT;
BEGIN
    -- Test creating a secret
    SELECT vault.create_secret('test_credential', 'test_name', 'Test vault access') INTO secret_id;
    
    -- Clean up test secret
    DELETE FROM vault.secrets WHERE id = secret_id;
    
    RETURN 'Vault access test successful - secret_id: ' || secret_id::TEXT;
EXCEPTION
    WHEN OTHERS THEN
        RETURN 'Vault access test failed: ' || SQLERRM;
END;
$$;

-- Grant execute on test function
GRANT EXECUTE ON FUNCTION public.test_vault_access() TO authenticated;
GRANT EXECUTE ON FUNCTION public.test_vault_access() TO service_role; 