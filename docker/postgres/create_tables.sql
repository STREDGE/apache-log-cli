SET enable_seqscan = off;

CREATE TABLE logs (
    id uuid default gen_random_uuid(),
    ip cidr not null,
    timestamp timestamptz not null,
    message varchar(60) not null
);

CREATE INDEX ip_idx ON logs USING gist(ip inet_ops);
