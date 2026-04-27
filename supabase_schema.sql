-- Execute no Supabase → SQL Editor → New Query

create table if not exists promos_enviadas (
  id         bigint generated always as identity primary key,
  hash       text not null,
  titulo     text,
  fonte      text,
  preco      numeric(10,2),
  data       date not null,
  created_at timestamptz default now()
);

-- Índice para busca rápida por hash
create index if not exists idx_promos_hash on promos_enviadas(hash, data);

-- Política de acesso
alter table promos_enviadas enable row level security;

create policy "leitura publica"   on promos_enviadas for select using (true);
create policy "insercao service"  on promos_enviadas for insert with check (true);
