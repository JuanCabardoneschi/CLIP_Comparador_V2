--
-- PostgreSQL database dump
--

\restrict 8vocGPztiga7rQ2FWNk91drSiyNDTOuvnRpmSSWHgxeGxMYvMhzdMhf6ZxLtLnw

-- Dumped from database version 17.6 (Debian 17.6-2.pgdg13+1)
-- Dumped by pg_dump version 18.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: api_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_keys (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    client_id uuid,
    key_name character varying(255) NOT NULL,
    api_key character varying(255) NOT NULL,
    is_active boolean DEFAULT true,
    requests_made integer DEFAULT 0,
    rate_limit integer DEFAULT 100,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_used timestamp without time zone
);


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    client_id uuid,
    name character varying(255) NOT NULL,
    description text,
    slug character varying(255) NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    name_en character varying(255),
    alternative_terms text,
    clip_prompt text,
    visual_features text,
    confidence_threshold numeric(3,2) DEFAULT 0.5,
    color character varying(50),
    centroid_embedding text,
    centroid_updated_at timestamp without time zone,
    centroid_image_count integer DEFAULT 0
);


--
-- Name: clients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clients (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name character varying(255) NOT NULL,
    domain character varying(255),
    status character varying(50) DEFAULT 'active'::character varying,
    plan character varying(50) DEFAULT 'starter'::character varying,
    monthly_searches integer DEFAULT 0,
    search_limit integer DEFAULT 1000,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    slug character varying(100),
    email character varying(255),
    description text,
    industry character varying(100),
    api_key character varying(100),
    api_settings text,
    is_active boolean DEFAULT true,
    category_confidence_threshold integer DEFAULT 70,
    product_similarity_threshold integer DEFAULT 30,
    CONSTRAINT clients_category_confidence_threshold_check CHECK (((category_confidence_threshold >= 1) AND (category_confidence_threshold <= 100))),
    CONSTRAINT clients_product_similarity_threshold_check CHECK (((product_similarity_threshold >= 1) AND (product_similarity_threshold <= 100)))
);


--
-- Name: image_embeddings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.image_embeddings (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    image_id uuid,
    embedding_vector double precision[],
    model_version character varying(50) DEFAULT 'ViT-B/16'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: images; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.images (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    client_id uuid,
    product_id uuid,
    filename character varying(255) NOT NULL,
    cloudinary_url text,
    cloudinary_public_id character varying(255),
    original_filename character varying(500),
    file_size integer,
    width integer,
    height integer,
    format character varying(50),
    is_primary boolean DEFAULT false,
    uploaded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    base64_data text,
    mime_type character varying(100),
    alt_text character varying(255),
    display_order integer DEFAULT 0,
    is_processed boolean DEFAULT false,
    clip_embedding text,
    upload_status character varying(50) DEFAULT 'pending'::character varying,
    error_message text,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: product_attribute_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_attribute_config (
    id integer NOT NULL,
    client_id uuid NOT NULL,
    key character varying(100) NOT NULL,
    label character varying(200) NOT NULL,
    type character varying(20) NOT NULL,
    required boolean DEFAULT false,
    options jsonb,
    field_order integer DEFAULT 0,
    expose_in_search boolean DEFAULT false
);


--
-- Name: product_attribute_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_attribute_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_attribute_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_attribute_config_id_seq OWNED BY public.product_attribute_config.id;


--
-- Name: products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.products (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    client_id uuid,
    category_id uuid,
    name character varying(255) NOT NULL,
    description text,
    price numeric(10,2),
    sku character varying(255),
    brand character varying(255),
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    stock integer DEFAULT 0,
    tags text,
    attributes jsonb
);


--
-- Name: store_search_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.store_search_config (
    store_id uuid NOT NULL,
    visual_weight double precision DEFAULT 0.6 NOT NULL,
    metadata_weight double precision DEFAULT 0.3 NOT NULL,
    business_weight double precision DEFAULT 0.1 NOT NULL,
    metadata_config jsonb DEFAULT '{"brand_weight": 1.0, "color_weight": 1.0, "style_weight": 0.6, "pattern_weight": 0.8, "material_weight": 0.7}'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'utc'::text),
    updated_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'utc'::text)
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255),
    role character varying(50) DEFAULT 'client_admin'::character varying,
    client_id uuid,
    is_active boolean DEFAULT true,
    last_login timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: product_attribute_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_attribute_config ALTER COLUMN id SET DEFAULT nextval('public.product_attribute_config_id_seq'::regclass);


--
-- Name: api_keys api_keys_api_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_api_key_key UNIQUE (api_key);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: categories categories_client_id_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_client_id_slug_key UNIQUE (client_id, slug);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id);


--
-- Name: image_embeddings image_embeddings_image_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_embeddings
    ADD CONSTRAINT image_embeddings_image_id_key UNIQUE (image_id);


--
-- Name: image_embeddings image_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_embeddings
    ADD CONSTRAINT image_embeddings_pkey PRIMARY KEY (id);


--
-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (id);


--
-- Name: product_attribute_config product_attribute_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_attribute_config
    ADD CONSTRAINT product_attribute_config_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: store_search_config store_search_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_search_config
    ADD CONSTRAINT store_search_config_pkey PRIMARY KEY (store_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_attr_config_client; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_attr_config_client ON public.product_attribute_config USING btree (client_id);


--
-- Name: idx_categories_client_centroid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_categories_client_centroid ON public.categories USING btree (client_id) WHERE (centroid_embedding IS NOT NULL);


--
-- Name: idx_products_client_cat_color_jsonb; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_products_client_cat_color_jsonb ON public.products USING btree (client_id, category_id, upper(TRIM(BOTH FROM (attributes ->> 'color'::text))));


--
-- Name: idx_products_color_jsonb; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_products_color_jsonb ON public.products USING btree (upper(TRIM(BOTH FROM (attributes ->> 'color'::text))));


--
-- Name: idx_store_search_config_store_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_store_search_config_store_id ON public.store_search_config USING btree (store_id);


--
-- Name: uq_attr_config_client_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_attr_config_client_key ON public.product_attribute_config USING btree (client_id, key);


--
-- Name: api_keys api_keys_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: categories categories_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: store_search_config fk_store_search_config_client; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_search_config
    ADD CONSTRAINT fk_store_search_config_client FOREIGN KEY (store_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: image_embeddings image_embeddings_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_embeddings
    ADD CONSTRAINT image_embeddings_image_id_fkey FOREIGN KEY (image_id) REFERENCES public.images(id) ON DELETE CASCADE;


--
-- Name: images images_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: images images_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- Name: product_attribute_config product_attribute_config_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_attribute_config
    ADD CONSTRAINT product_attribute_config_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: products products_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE SET NULL;


--
-- Name: products products_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: users users_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 8vocGPztiga7rQ2FWNk91drSiyNDTOuvnRpmSSWHgxeGxMYvMhzdMhf6ZxLtLnw

