-- Edge Function deploy edildikten sonra Supabase SQL Editor'de bir kez çalıştırılır.
-- project_url ve service_role_key değerlerini Supabase Vault'a kaydedin.
select vault.create_secret('https://PROJECT_REF.supabase.co', 'project_url');
select vault.create_secret('SERVICE_ROLE_KEY', 'service_role_key');

select cron.schedule(
  'nova-simulation-orders-5min',
  '*/5 * * * *',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url') || '/functions/v1/process-simulation-orders',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'service_role_key')
    ),
    body := '{}'::jsonb
  );
  $$
);
