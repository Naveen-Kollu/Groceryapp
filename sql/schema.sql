create extension if not exists pgcrypto;

create table if not exists public.categories (
    id text primary key,
    name text not null unique,
    slug text not null unique,
    sort_order integer not null default 0
);

create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    category_id text not null references public.categories(id) on update cascade on delete restrict,
    name text not null,
    description text not null default '',
    price numeric(12, 2) not null check (price >= 0),
    unit text not null default 'each',
    stock_quantity integer not null default 0 check (stock_quantity >= 0),
    image_url text not null default '',
    is_available boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (category_id, name)
);

create table if not exists public.delivery_locations (
    id text primary key,
    name text not null unique
);

insert into public.delivery_locations (id, name) values
    ('skullerud', 'Skullerud'),
    ('solli', 'Solli'),
    ('sagane', 'Sagane'),
    ('fornebu', 'Fornebu'),
    ('veitvet', 'Veitvet')
on conflict (id) do update set name = excluded.name;

create table if not exists public.product_location_inventory (
    product_id uuid not null references public.products(id) on delete cascade,
    location_id text not null references public.delivery_locations(id) on delete cascade,
    stock_quantity integer not null default 0 check (stock_quantity >= 0),
    updated_at timestamptz not null default now(),
    primary key (product_id, location_id)
);

create table if not exists public.customer_orders (
    id uuid primary key default gen_random_uuid(),
    customer_name text not null,
    customer_phone text not null,
    customer_email text,
    sms_consent boolean not null default false,
    delivery_address text not null,
    delivery_location_id text references public.delivery_locations(id),
    total numeric(12, 2) not null default 0 check (total >= 0),
    status text not null default 'placed' check (status in ('placed', 'confirmed', 'packing', 'out_for_delivery', 'completed', 'cancelled')),
    created_at timestamptz not null default now()
);

alter table public.customer_orders
    add column if not exists delivery_location_id text references public.delivery_locations(id);
alter table public.customer_orders
    add column if not exists sms_consent boolean not null default false;

create table if not exists public.market_admin_users (
    id uuid primary key default gen_random_uuid(),
    username text not null unique,
    display_name text not null,
    password_hash text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.market_admin_user_locations (
    user_id uuid not null references public.market_admin_users(id) on delete cascade,
    location_id text not null references public.delivery_locations(id) on delete cascade,
    primary key (user_id, location_id)
);

create table if not exists public.order_items (
    id uuid primary key default gen_random_uuid(),
    order_id uuid not null references public.customer_orders(id) on delete cascade,
    product_id uuid references public.products(id) on delete set null,
    product_name text not null,
    quantity integer not null check (quantity > 0),
    unit_price numeric(12, 2) not null check (unit_price >= 0),
    line_total numeric(12, 2) generated always as (quantity * unit_price) stored
);

alter table public.order_items
    alter column product_id drop not null;
alter table public.order_items
    drop constraint if exists order_items_product_id_fkey;
alter table public.order_items
    add constraint order_items_product_id_fkey
    foreign key (product_id) references public.products(id) on delete set null;

create table if not exists public.customer_item_requests (
    id uuid primary key default gen_random_uuid(),
    customer_name text not null,
    customer_phone text not null,
    requested_name text not null,
    category_id text references public.categories(id),
    delivery_location_id text references public.delivery_locations(id),
    delivery_address text,
    note text,
    status text not null default 'new' check (status in ('new', 'reviewing', 'added', 'unavailable')),
    created_at timestamptz not null default now()
);

alter table public.customer_item_requests
    add column if not exists category_id text references public.categories(id);
alter table public.customer_item_requests
    add column if not exists delivery_location_id text references public.delivery_locations(id);
alter table public.customer_item_requests
    add column if not exists delivery_address text;

insert into public.categories (id, name, slug, sort_order) values
    ('vegetables', 'Indian Breakfast', 'indian-breakfast', 1),
    ('fruits', 'Indian Snacks', 'indian-snacks', 2),
    ('indian-lunch-dinner', 'Indian Lunch/Dinner', 'indian-lunch-dinner', 3),
    ('lentils', 'Lentils & pulses', 'lentils', 4),
    ('grains', 'Rice & grains', 'grains', 5),
    ('pantry', 'Pantry', 'pantry', 6)
on conflict (id) do update set
    name = excluded.name,
    slug = excluded.slug,
    sort_order = excluded.sort_order;

update public.products set
    name = 'Idli & sambar',
    description = 'Soft steamed rice cakes with lentil stew',
    price = 6.50,
    unit = 'portion',
    image_url = 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=700&q=80'
where category_id = 'vegetables' and name = 'Vine tomatoes';
update public.products set
    name = 'Masala dosa',
    description = 'Crispy dosa with spiced potato filling',
    price = 7.50,
    unit = 'portion',
    image_url = 'https://images.unsplash.com/photo-1668236543090-82eba5ee5976?auto=format&fit=crop&w=700&q=80'
where category_id = 'vegetables' and name = 'Baby spinach';
update public.products set
    name = 'Vegetable samosa',
    description = 'Crisp pastry filled with spiced potato',
    price = 2.50,
    unit = '2 pieces',
    image_url = 'https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=700&q=80'
where category_id = 'fruits' and name = 'Gala apples';
update public.products set
    name = 'Onion pakora',
    description = 'Crispy onion fritters with Indian spices',
    price = 4.50,
    unit = 'portion',
    image_url = 'https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=700&q=80'
where category_id = 'fruits' and name = 'Navel oranges';

insert into public.products (category_id, name, description, price, unit, stock_quantity, image_url) values
    ('vegetables', 'Idli & sambar', 'Soft steamed rice cakes with lentil stew', 6.50, 'portion', 18, 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=700&q=80'),
    ('vegetables', 'Masala dosa', 'Crispy dosa with spiced potato filling', 7.50, 'portion', 12, 'https://images.unsplash.com/photo-1668236543090-82eba5ee5976?auto=format&fit=crop&w=700&q=80'),
    ('fruits', 'Vegetable samosa', 'Crisp pastry filled with spiced potato', 2.50, '2 pieces', 20, 'https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=700&q=80'),
    ('fruits', 'Onion pakora', 'Crispy onion fritters with Indian spices', 4.50, 'portion', 14, 'https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=700&q=80'),
    ('indian-lunch-dinner', 'Vegetable biryani', 'Fragrant basmati rice with vegetables and spices', 10.90, 'portion', 15, 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=700&q=80'),
    ('indian-lunch-dinner', 'Paneer curry', 'Paneer in a creamy tomato curry', 11.50, 'portion', 10, 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=700&q=80'),
    ('lentils', 'Red lentils', 'Quick-cooking, protein-rich', 4.60, '500 g', 16, 'https://images.unsplash.com/photo-1515543904379-3d757afe72e4?auto=format&fit=crop&w=700&q=80'),
    ('lentils', 'Chickpeas', 'Creamy, versatile pantry staple', 3.85, '500 g', 9, 'https://images.unsplash.com/photo-1515543904379-3d757afe72e4?auto=format&fit=crop&w=700&q=80'),
    ('grains', 'Basmati rice', 'Fragrant long grain, aged', 8.50, '2 kg', 10, 'https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=700&q=80'),
    ('grains', 'Rolled oats', 'Wholegrain breakfast oats', 3.40, '1 kg', 0, 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=700&q=80'),
    ('pantry', 'Extra virgin olive oil', 'Cold pressed, smooth finish', 9.90, '500 ml', 7, 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?auto=format&fit=crop&w=700&q=80')
on conflict do nothing;

insert into public.product_location_inventory (product_id, location_id, stock_quantity)
select id, 'skullerud', stock_quantity from public.products
on conflict (product_id, location_id) do nothing;

update public.products set stock_quantity = 0 where stock_quantity <> 0;

alter table public.categories enable row level security;
alter table public.products enable row level security;
alter table public.delivery_locations enable row level security;
alter table public.product_location_inventory enable row level security;
alter table public.customer_orders enable row level security;
alter table public.order_items enable row level security;
alter table public.customer_item_requests enable row level security;
alter table public.market_admin_users enable row level security;
alter table public.market_admin_user_locations enable row level security;

drop policy if exists "Catalog categories are readable" on public.categories;
create policy "Catalog categories are readable" on public.categories for select to anon, authenticated using (true);
drop policy if exists "Available products are readable" on public.products;
create policy "Available products are readable" on public.products for select to anon, authenticated using (is_available = true);

create or replace function public.create_market_admin_user(
    p_username text,
    p_display_name text,
    p_password_hash text,
    p_location_ids text[]
) returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    new_user_id uuid;
begin
    if p_location_ids is null or cardinality(p_location_ids) < 1 or cardinality(p_location_ids) > 5
       or cardinality(p_location_ids) <> (select count(distinct requested.location_id) from unnest(p_location_ids) as requested(location_id))
       or exists (
           select 1 from unnest(p_location_ids) as requested(location_id)
           where not exists (select 1 from public.delivery_locations where id = requested.location_id)
       ) then
        raise exception 'Choose one or more valid delivery locations.';
    end if;

    insert into public.market_admin_users (username, display_name, password_hash)
    values (lower(trim(p_username)), trim(p_display_name), p_password_hash)
    returning id into new_user_id;

    insert into public.market_admin_user_locations (user_id, location_id)
    select new_user_id, requested.location_id from unnest(p_location_ids) as requested(location_id);

    return new_user_id;
end;
$$;

revoke all on function public.create_market_admin_user(text, text, text, text[]) from public, anon, authenticated;
grant execute on function public.create_market_admin_user(text, text, text, text[]) to service_role;

create or replace function public.replace_market_admin_locations(p_user_id uuid, p_location_ids text[])
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
    if not exists (select 1 from public.market_admin_users where id = p_user_id) then
        return false;
    end if;
    if p_location_ids is null or cardinality(p_location_ids) < 1 or cardinality(p_location_ids) > 5
       or cardinality(p_location_ids) <> (select count(distinct requested.location_id) from unnest(p_location_ids) as requested(location_id))
       or exists (
           select 1 from unnest(p_location_ids) as requested(location_id)
           where not exists (select 1 from public.delivery_locations where id = requested.location_id)
       ) then
        raise exception 'Choose one or more valid delivery locations.';
    end if;

    delete from public.market_admin_user_locations where user_id = p_user_id;
    insert into public.market_admin_user_locations (user_id, location_id)
    select p_user_id, requested.location_id from unnest(p_location_ids) as requested(location_id);
    return true;
end;
$$;

revoke all on function public.replace_market_admin_locations(uuid, text[]) from public, anon, authenticated;
grant execute on function public.replace_market_admin_locations(uuid, text[]) to service_role;

create or replace function public.create_market_product(
    p_category_id text,
    p_name text,
    p_description text,
    p_price numeric,
    p_unit text,
    p_image_url text,
    p_location_stock jsonb
) returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    new_product_id uuid;
    stock_entry record;
    stock_value integer;
begin
    if nullif(trim(p_name), '') is null or nullif(trim(p_unit), '') is null
       or p_price is null or p_price <= 0 then
        raise exception 'Product name, unit, and a positive price are required.';
    end if;
    if p_location_stock is null or jsonb_typeof(p_location_stock) is distinct from 'object'
       or (select count(*) from jsonb_object_keys(p_location_stock)) < 1
       or (select count(*) from jsonb_object_keys(p_location_stock)) > 5 then
        raise exception 'Select between one and five locations with starting stock.';
    end if;

    for stock_entry in select key, value from jsonb_each(p_location_stock)
    loop
        if not exists (
            select 1 from public.delivery_locations where id = stock_entry.key
        ) or jsonb_typeof(stock_entry.value) is distinct from 'number' then
            raise exception 'Choose only valid delivery locations and stock quantities.';
        end if;
        stock_value := (stock_entry.value #>> '{}')::integer;
        if stock_value < 1 or stock_value > 1000000
           or (stock_entry.value #>> '{}')::numeric <> stock_value then
            raise exception 'Selected locations must have between 1 and 1,000,000 items in stock.';
        end if;
    end loop;

    insert into public.products (category_id, name, description, price, unit, image_url, stock_quantity)
    values (p_category_id, trim(p_name), coalesce(trim(p_description), ''),
        p_price, trim(p_unit), coalesce(trim(p_image_url), ''), 0)
    returning id into new_product_id;

    insert into public.product_location_inventory (product_id, location_id, stock_quantity)
    select new_product_id, requested.key, (requested.value #>> '{}')::integer
    from jsonb_each(p_location_stock) as requested;

    return new_product_id;
end;
$$;

revoke all on function public.create_market_product(text, text, text, numeric, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.create_market_product(text, text, text, numeric, text, text, jsonb) to service_role;

drop function if exists public.place_order(text, text, text, text, jsonb);
drop function if exists public.place_order(text, text, text, text, text, jsonb);

create or replace function public.place_order(
    p_customer_name text,
    p_customer_phone text,
    p_customer_email text,
    p_sms_consent boolean,
    p_delivery_address text,
    p_delivery_location_id text,
    p_items jsonb
) returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    new_order_id uuid;
    item jsonb;
    product_row public.products%rowtype;
    item_quantity integer;
    inventory_quantity integer;
    order_total numeric(12, 2) := 0;
begin
    if p_items is null or jsonb_typeof(p_items) is distinct from 'array' then
        raise exception 'Order items must be provided as an array.';
    end if;
    if jsonb_array_length(p_items) = 0 then
        raise exception 'An order must contain at least one item.';
    end if;

    if not exists (select 1 from public.delivery_locations where id = p_delivery_location_id) then
        raise exception 'A valid delivery location must be selected.';
    end if;

    insert into public.customer_orders (
        customer_name, customer_phone, customer_email, sms_consent, delivery_address, delivery_location_id
    )
    values (
        trim(p_customer_name), trim(p_customer_phone), nullif(trim(p_customer_email), ''),
        coalesce(p_sms_consent, false), trim(p_delivery_address), p_delivery_location_id
    )
    returning id into new_order_id;

    for item in select value from jsonb_array_elements(p_items)
    loop
        item_quantity := (item->>'quantity')::integer;
        if item_quantity < 1 or item_quantity > 99 then
            raise exception 'Item quantity must be between 1 and 99.';
        end if;

        select * into product_row
        from public.products
        where id = (item->>'product_id')::uuid and is_available = true
        for update;

        if not found then
            raise exception 'A requested item is unavailable or out of stock.';
        end if;

        select stock_quantity into inventory_quantity
        from public.product_location_inventory
        where product_id = product_row.id and location_id = p_delivery_location_id
        for update;

        if not found or inventory_quantity < item_quantity then
            raise exception 'A requested item is unavailable or out of stock at the selected location.';
        end if;

        insert into public.order_items (order_id, product_id, product_name, quantity, unit_price)
        values (new_order_id, product_row.id, product_row.name, item_quantity, product_row.price);

        update public.product_location_inventory
        set stock_quantity = stock_quantity - item_quantity, updated_at = now()
        where product_id = product_row.id and location_id = p_delivery_location_id;

        order_total := order_total + (product_row.price * item_quantity);
    end loop;

    update public.customer_orders set total = order_total where id = new_order_id;
    return new_order_id;
end;
$$;

revoke all on function public.place_order(text, text, text, boolean, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.place_order(text, text, text, boolean, text, text, jsonb) to service_role;

drop function if exists public.lookup_order_status(text);

create function public.lookup_order_status(p_order_number text)
returns table(order_number text, status text, delivery_location text, created_at timestamptz)
language plpgsql
security definer
set search_path = public
as $$
begin
    if p_order_number !~* '^[0-9a-f]{8}$' then
        return;
    end if;

    return query
    select left(customer_orders.id::text, 8), customer_orders.status,
        coalesce(delivery_locations.name, 'Unassigned'), customer_orders.created_at
    from public.customer_orders
    left join public.delivery_locations on delivery_locations.id = customer_orders.delivery_location_id
    where left(customer_orders.id::text, 8) = lower(p_order_number)
    order by customer_orders.created_at desc
    limit 2;
end;
$$;

revoke all on function public.lookup_order_status(text) from public, anon, authenticated;
grant execute on function public.lookup_order_status(text) to anon, authenticated;

notify pgrst, 'reload schema';
