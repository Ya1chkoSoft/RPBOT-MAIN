--
-- PostgreSQL database dump
--

\restrict bnrcw0Iu433GAE8oYS0XvwEgqlnfKQiGBWSsKAjbD9VavYDj9IjLkSUs1rCO01x

-- Dumped from database version 18.1
-- Dumped by pg_dump version 18.1

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admins; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.admins (
    user_id bigint NOT NULL,
    userfullname character varying,
    username character varying,
    adminlevel integer NOT NULL,
    CONSTRAINT check_admin_level CHECK (((adminlevel >= 0) AND (adminlevel <= 4)))
);


ALTER TABLE public.admins OWNER TO "Ya1chko";

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO "Ya1chko";

--
-- Name: country_blacklist; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.country_blacklist (
    id bigint NOT NULL,
    country_id bigint NOT NULL,
    user_id bigint NOT NULL,
    admin_id bigint NOT NULL,
    is_perm_ban boolean NOT NULL,
    reason character varying
);


ALTER TABLE public.country_blacklist OWNER TO "Ya1chko";

--
-- Name: country_blacklist_id_seq; Type: SEQUENCE; Schema: public; Owner: Ya1chko
--

CREATE SEQUENCE public.country_blacklist_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.country_blacklist_id_seq OWNER TO "Ya1chko";

--
-- Name: country_blacklist_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: Ya1chko
--

ALTER SEQUENCE public.country_blacklist_id_seq OWNED BY public.country_blacklist.id;


--
-- Name: country_reviews; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.country_reviews (
    review_id integer NOT NULL,
    user_id bigint NOT NULL,
    country_id bigint NOT NULL,
    rating integer NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.country_reviews OWNER TO "Ya1chko";

--
-- Name: country_reviews_review_id_seq; Type: SEQUENCE; Schema: public; Owner: Ya1chko
--

CREATE SEQUENCE public.country_reviews_review_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.country_reviews_review_id_seq OWNER TO "Ya1chko";

--
-- Name: country_reviews_review_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: Ya1chko
--

ALTER SEQUENCE public.country_reviews_review_id_seq OWNED BY public.country_reviews.review_id;


--
-- Name: history; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.history (
    id integer NOT NULL,
    admin_id bigint,
    target_id bigint NOT NULL,
    event_type character varying(32) NOT NULL,
    points integer NOT NULL,
    reason character varying(512) NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.history OWNER TO "Ya1chko";

--
-- Name: history_id_seq; Type: SEQUENCE; Schema: public; Owner: Ya1chko
--

CREATE SEQUENCE public.history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.history_id_seq OWNER TO "Ya1chko";

--
-- Name: history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: Ya1chko
--

ALTER SEQUENCE public.history_id_seq OWNED BY public.history.id;


--
-- Name: meme_countries; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.meme_countries (
    country_id bigint NOT NULL,
    ruler_id bigint NOT NULL,
    chat_id bigint NOT NULL,
    name character varying(100) NOT NULL,
    memename character varying(100) NOT NULL,
    description character varying(1000),
    ideology character varying(100),
    avatar_url character varying(255),
    "position" character varying(50) NOT NULL,
    map_url character varying(2048),
    influence_points integer NOT NULL,
    avg_rating double precision NOT NULL,
    total_reviews integer NOT NULL,
    tax_rate double precision DEFAULT '0'::double precision NOT NULL,
    treasury bigint DEFAULT '0'::bigint NOT NULL,
    flag_file_id character varying(255),
    map_file_id character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    country_url character varying(255)
);


ALTER TABLE public.meme_countries OWNER TO "Ya1chko";

--
-- Name: meme_countries_country_id_seq; Type: SEQUENCE; Schema: public; Owner: Ya1chko
--

CREATE SEQUENCE public.meme_countries_country_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.meme_countries_country_id_seq OWNER TO "Ya1chko";

--
-- Name: meme_countries_country_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: Ya1chko
--

ALTER SEQUENCE public.meme_countries_country_id_seq OWNED BY public.meme_countries.country_id;


--
-- Name: punishments; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.punishments (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    admin_id bigint,
    action_type character varying NOT NULL,
    reason character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    expires_at timestamp without time zone,
    is_active boolean NOT NULL
);


ALTER TABLE public.punishments OWNER TO "Ya1chko";

--
-- Name: punishments_id_seq; Type: SEQUENCE; Schema: public; Owner: Ya1chko
--

CREATE SEQUENCE public.punishments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.punishments_id_seq OWNER TO "Ya1chko";

--
-- Name: punishments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: Ya1chko
--

ALTER SEQUENCE public.punishments_id_seq OWNED BY public.punishments.id;


--
-- Name: reserved_country_names; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.reserved_country_names (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    added_by bigint NOT NULL,
    added_at timestamp without time zone NOT NULL
);


ALTER TABLE public.reserved_country_names OWNER TO "Ya1chko";

--
-- Name: reserved_country_names_id_seq; Type: SEQUENCE; Schema: public; Owner: Ya1chko
--

CREATE SEQUENCE public.reserved_country_names_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reserved_country_names_id_seq OWNER TO "Ya1chko";

--
-- Name: reserved_country_names_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: Ya1chko
--

ALTER SEQUENCE public.reserved_country_names_id_seq OWNED BY public.reserved_country_names.id;


--
-- Name: rp_events; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.rp_events (
    event_id integer NOT NULL,
    admin_id bigint NOT NULL,
    chat_id bigint NOT NULL,
    title character varying(100) NOT NULL,
    description text,
    status character varying(20) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    finished_at timestamp without time zone
);


ALTER TABLE public.rp_events OWNER TO "Ya1chko";

--
-- Name: rp_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: Ya1chko
--

CREATE SEQUENCE public.rp_events_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rp_events_event_id_seq OWNER TO "Ya1chko";

--
-- Name: rp_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: Ya1chko
--

ALTER SEQUENCE public.rp_events_event_id_seq OWNED BY public.rp_events.event_id;


--
-- Name: rp_participants; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.rp_participants (
    participant_id integer NOT NULL,
    event_id integer NOT NULL,
    user_id bigint NOT NULL,
    joined_at timestamp without time zone NOT NULL
);


ALTER TABLE public.rp_participants OWNER TO "Ya1chko";

--
-- Name: rp_participants_participant_id_seq; Type: SEQUENCE; Schema: public; Owner: Ya1chko
--

CREATE SEQUENCE public.rp_participants_participant_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rp_participants_participant_id_seq OWNER TO "Ya1chko";

--
-- Name: rp_participants_participant_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: Ya1chko
--

ALTER SEQUENCE public.rp_participants_participant_id_seq OWNED BY public.rp_participants.participant_id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: Ya1chko
--

CREATE TABLE public.users (
    user_id bigint NOT NULL,
    userfullname character varying,
    username character varying,
    points integer NOT NULL,
    "position" character varying(50) NOT NULL,
    is_ruler boolean NOT NULL,
    last_country_creation timestamp without time zone,
    last_country_deletion timestamp without time zone,
    adminlevel integer NOT NULL,
    country_id bigint,
    lost_in_casino integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.users OWNER TO "Ya1chko";

--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: Ya1chko
--

CREATE SEQUENCE public.users_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_user_id_seq OWNER TO "Ya1chko";

--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: Ya1chko
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- Name: country_blacklist id; Type: DEFAULT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_blacklist ALTER COLUMN id SET DEFAULT nextval('public.country_blacklist_id_seq'::regclass);


--
-- Name: country_reviews review_id; Type: DEFAULT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_reviews ALTER COLUMN review_id SET DEFAULT nextval('public.country_reviews_review_id_seq'::regclass);


--
-- Name: history id; Type: DEFAULT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.history ALTER COLUMN id SET DEFAULT nextval('public.history_id_seq'::regclass);


--
-- Name: meme_countries country_id; Type: DEFAULT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.meme_countries ALTER COLUMN country_id SET DEFAULT nextval('public.meme_countries_country_id_seq'::regclass);


--
-- Name: punishments id; Type: DEFAULT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.punishments ALTER COLUMN id SET DEFAULT nextval('public.punishments_id_seq'::regclass);


--
-- Name: reserved_country_names id; Type: DEFAULT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.reserved_country_names ALTER COLUMN id SET DEFAULT nextval('public.reserved_country_names_id_seq'::regclass);


--
-- Name: rp_events event_id; Type: DEFAULT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.rp_events ALTER COLUMN event_id SET DEFAULT nextval('public.rp_events_event_id_seq'::regclass);


--
-- Name: rp_participants participant_id; Type: DEFAULT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.rp_participants ALTER COLUMN participant_id SET DEFAULT nextval('public.rp_participants_participant_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- Data for Name: admins; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.admins (user_id, userfullname, username, adminlevel) FROM stdin;
6777326894	\N	\N	4
6262100430	\N	\N	2
6051072463	\N	\N	1
924296512	\N	\N	2
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.alembic_version (version_num) FROM stdin;
10e0dceb000a
\.


--
-- Data for Name: country_blacklist; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.country_blacklist (id, country_id, user_id, admin_id, is_perm_ban, reason) FROM stdin;
\.


--
-- Data for Name: country_reviews; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.country_reviews (review_id, user_id, country_id, rating, created_at) FROM stdin;
1	1735359418	3	5	2026-01-02 13:28:12.870125
2	6265630174	3	5	2026-01-02 13:28:18.664556
3	8552036745	4	4	2026-01-02 13:47:59.429651
\.


--
-- Data for Name: history; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.history (id, admin_id, target_id, event_type, points, reason, "timestamp") FROM stdin;
1	\N	8451399261	JOIN_COUNTRY	0	Вступление в страну: ТЕЕЕЕСТ	2025-12-28 03:28:04.073842
3	5245484303	6777326894	penalty	5	Без причины	2025-12-28 18:02:34.349403
8	\N	6283690984	JOIN_COUNTRY	0	Вступление в страну: ◼️Аторния◼️	2026-01-02 12:15:51.959016
9	\N	5667570277	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-02 12:30:23.510307
10	\N	6045713401	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-02 12:34:33.465992
11	\N	5742270445	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-02 12:37:31.071556
12	\N	1996901470	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-02 12:38:49.671564
13	\N	8183676732	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-02 12:48:58.129787
18	5245484303	5245484303	admin_give	15	Без причины	2026-01-02 13:05:07.510809
20	\N	1735359418	JOIN_COUNTRY	0	Вступление в страну: ◼️Аторния◼️	2026-01-02 13:17:38.306171
21	\N	1202482849	JOIN_COUNTRY	0	Вступление в страну: ◼️Аторния◼️	2026-01-02 13:17:48.449272
22	\N	6265630174	JOIN_COUNTRY	0	Вступление в страну: ◼️Аторния◼️	2026-01-02 13:18:10.530889
23	\N	8552036745	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-02 13:33:21.789339
25	\N	6513250501	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-02 13:44:39.605849
26	\N	6608663108	JOIN_COUNTRY	0	Вступление в страну: ◼️Аторния◼️	2026-01-02 13:44:47.821983
31	5007147634	5007147634	CASINO_GAME	2	Казино: Слоты	2026-01-02 13:53:12.163493
32	5007147634	5007147634	CASINO_GAME	4	Казино: Слоты	2026-01-02 13:54:16.909857
33	5007147634	5007147634	CASINO_GAME	2	Казино: Слоты	2026-01-02 13:55:15.358494
34	1180169608	1180169608	CASINO_GAME	-10	Казино: Слоты	2026-01-02 13:58:22.476546
35	5007147634	5007147634	CASINO_GAME	-1	Казино: Слоты	2026-01-02 14:06:58.184453
36	5007147634	5007147634	CASINO_GAME	-1	Казино: Слоты	2026-01-02 14:07:14.125472
37	977008008	977008008	CASINO_GAME	3	Казино: Слоты	2026-01-02 14:48:36.25656
38	977008008	977008008	CASINO_GAME	2	Казино: Слоты	2026-01-02 14:48:51.131556
39	977008008	977008008	CASINO_GAME	3	Казино: Слоты	2026-01-02 14:49:03.623553
40	977008008	977008008	CASINO_GAME	1	Казино: Слоты	2026-01-02 14:49:23.505556
41	977008008	977008008	CASINO_GAME	-2	Казино: Слоты	2026-01-02 14:50:14.167153
42	977008008	977008008	CASINO_GAME	-1	Казино: Слоты	2026-01-02 14:50:43.043843
43	1180169608	1180169608	CASINO_GAME	-5	Казино: Слоты	2026-01-02 14:52:19.240494
44	\N	5922612105	JOIN_COUNTRY	0	Вступление в страну: ◼️Аторния◼️	2026-01-02 14:54:07.771237
45	1180169608	1180169608	CASINO_GAME	-5	Казино: Слоты	2026-01-02 14:54:13.400525
46	\N	1625137625	JOIN_COUNTRY	0	Вступление в страну: ◼️Аторния◼️	2026-01-02 14:54:33.386744
47	\N	5139558597	JOIN_COUNTRY	0	Вступление в страну: РК Шварценбляхерштадт	2026-01-02 15:17:59.011789
48	\N	6001376284	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-02 21:18:46.162024
49	\N	8498559832	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-03 00:53:32.18027
50	\N	6893332028	JOIN_COUNTRY	0	Вступление в страну: ◼️Аторния◼️	2026-01-22 23:14:52.616216
51	5245484303	5245484303	SLOT_GAME	12	Казино: Слоты 3x3	2026-01-24 18:03:46.253982
52	5245484303	5245484303	SLOT_GAME	8	Казино: Слоты 3x3	2026-01-24 18:09:09.208243
53	5245484303	5245484303	SLOT_GAME	-5	Казино: Слоты 3x3	2026-01-24 19:17:22.463751
54	5245484303	5245484303	CASINO_GAME	13	Казино: Слоты	2026-01-24 19:28:40.467901
55	5245484303	5245484303	SLOT_GAME	10	Казино: Слоты 3x3	2026-01-24 19:29:30.285565
56	5245484303	5245484303	SLOT_GAME	26	Казино: Слоты 3x3	2026-01-24 19:29:54.080808
57	5245484303	5245484303	SLOT_GAME	68	Казино: Слоты 3x3	2026-01-24 19:30:05.290901
58	5245484303	5245484303	SLOT_GAME	106	Казино: Слоты 3x3	2026-01-24 19:30:14.727848
59	5245484303	5245484303	SLOT_GAME	94	Казино: Слоты 3x3	2026-01-24 19:30:23.408805
60	5245484303	5245484303	SLOT_GAME	111	Казино: Слоты 3x3	2026-01-24 19:30:39.055939
61	\N	7103274533	JOIN_COUNTRY	0	Вступление в страну: ◼️Аторния◼️	2026-01-24 19:35:25.806896
62	5245484303	5245484303	SLOT_GAME	285	Казино: Слоты 3x3	2026-01-24 23:34:33.674353
63	5245484303	5245484303	CASINO_GAME	10	Казино: Слоты	2026-01-25 01:40:18.364415
64	5245484303	5245484303	CASINO_GAME	-50	Казино: Слоты	2026-01-25 01:44:49.192524
65	5245484303	1689329449	admin_give	5	Без причины	2026-01-25 01:49:38.68652
66	5245484303	5245484303	SLOT_GAME	168	Казино: Слоты 3x3	2026-01-25 14:36:39.934547
67	5245484303	5245484303	SLOT_GAME	267	Казино: Слоты 3x3	2026-01-25 14:37:14.979256
68	5245484303	5245484303	SLOT_GAME	57	Казино: Слоты 3x3	2026-01-25 14:38:23.019746
69	5245484303	5245484303	SLOT_GAME	-50	Казино: Слоты 3x3	2026-01-25 23:06:36.425988
70	5245484303	5245484303	SLOT_GAME	816	Казино: Слоты 3x3	2026-01-25 23:11:01.895865
71	\N	924296512	JOIN_COUNTRY	0	Вступление в страну: Υπερβόρειο Χετμανάτο	2026-01-26 00:03:50.235676
72	\N	924296512	CHANGE_COUNTRY	0	Смена страны: Υπερβόρειο Χετμανάτο → ◼️Аторния◼️	2026-01-26 00:03:54.833443
73	\N	1996901470	CHANGE_COUNTRY	0	Смена страны: Υπερβόρειο Χετμανάτο → ◼️Аторния◼️	2026-01-26 00:37:59.029946
74	5245484303	5245484303	CASINO_GAME	100	Казино: Слоты	2026-01-26 01:16:01.084056
75	5245484303	5245484303	CASINO_GAME	-100	Казино: Слоты	2026-01-26 01:16:42.595684
76	5245484303	5245484303	SLOT_GAME	87	Казино: Слоты 3x3	2026-01-26 01:16:48.686107
77	1996901470	1996901470	SLOT_GAME	12	Казино: Слоты 3x3	2026-01-26 01:17:00.287929
78	1996901470	1996901470	SLOT_GAME	22	Казино: Слоты 3x3	2026-01-26 01:17:12.75761
79	5245484303	5245484303	SLOT_GAME	52	Казино: Слоты 3x3	2026-01-26 01:17:18.567173
80	1165712496	1165712496	SLOT_GAME	13	Казино: Слоты 3x3	2026-01-26 01:17:23.961276
81	1996901470	1996901470	SLOT_GAME	110	Казино: Слоты 3x3	2026-01-26 01:17:26.53183
82	5245484303	5245484303	SLOT_GAME	840	Казино: Слоты 3x3	2026-01-26 01:17:31.325944
84	1165712496	1165712496	CASINO_GAME	30	Казино: Слоты	2026-01-26 01:17:59.400713
89	5245484303	5245484303	admin_give	1000000	Без причины	2026-01-26 01:19:20.467984
91	5245484303	5245484303	CASINO_GAME	15000000	Казино: Слоты	2026-01-26 01:23:33.027713
95	5245484303	5245484303	SLOT_GAME	-14	Казино: Слоты 3x3	2026-01-26 01:24:54.396857
96	5245484303	5245484303	SLOT_GAME	-1	Казино: Слоты 3x3	2026-01-26 01:25:04.133522
98	1165712496	1165712496	SLOT_GAME	15	Казино: Слоты 3x3	2026-01-26 01:25:22.515703
100	5245484303	5245484303	SLOT_GAME	10	Казино: Слоты 3x3	2026-01-26 01:26:18.329383
101	924296512	924296512	SLOT_GAME	160	Казино: Слоты 3x3	2026-01-26 01:26:34.245467
83	1165712496	1165712496	CASINO_GAME	26	Казино: Слоты	2026-01-26 01:17:38.685526
85	1996901470	1996901470	SLOT_GAME	258	Казино: Слоты 3x3	2026-01-26 01:18:02.95084
86	1996901470	1996901470	SLOT_GAME	127	Казино: Слоты 3x3	2026-01-26 01:18:15.667948
87	1996901470	1996901470	SLOT_GAME	258	Казино: Слоты 3x3	2026-01-26 01:18:39.513495
88	1996901470	1996901470	SLOT_GAME	-403	Казино: Слоты 3x3	2026-01-26 01:19:19.112015
90	5245484303	5245484303	CASINO_GAME	5000000	Казино: Слоты	2026-01-26 01:19:29.556048
92	5245484303	5245484303	CASINO_GAME	60004680	Казино: Слоты	2026-01-26 01:24:00.888669
93	5245484303	5245484303	CASINO_GAME	-60004680	Казино: Слоты	2026-01-26 01:24:19.727791
94	5245484303	5245484303	admin_give	15	Без причины	2026-01-26 01:24:43.598436
97	1165712496	1165712496	CASINO_GAME	80	Казино: Слоты	2026-01-26 01:25:04.809809
99	5245484303	5245484303	SLOT_GAME	76	Казино: Слоты 3x3	2026-01-26 01:26:07.916602
102	5245484303	5245484303	CASINO_GAME	-5	Казино: Слоты	2026-01-26 01:26:42.221749
103	924296512	924296512	SLOT_GAME	166	Казино: Слоты 3x3	2026-01-26 01:26:43.842688
104	5245484303	5245484303	SLOT_GAME	-5	Казино: Слоты 3x3	2026-01-26 01:26:47.217999
105	924296512	924296512	SLOT_GAME	-67	Казино: Слоты 3x3	2026-01-26 01:26:49.669643
106	924296512	924296512	SLOT_GAME	128	Казино: Слоты 3x3	2026-01-26 01:26:58.313597
107	924296512	924296512	SLOT_GAME	-67	Казино: Слоты 3x3	2026-01-26 01:27:19.878239
108	5245484303	5245484303	admin_give	15	Без причины	2026-01-27 02:26:26.463114
109	5245484303	5245484303	SLOT_GAME	15	Казино: Слоты 3x3	2026-01-27 02:26:30.607628
110	5245484303	5245484303	SLOT_GAME	5	Казино: Слоты 3x3	2026-01-27 02:26:36.406708
111	5245484303	5245484303	SLOT_GAME	22	Казино: Слоты 3x3	2026-01-27 02:26:41.055453
112	5245484303	5245484303	SLOT_GAME	5	Казино: Слоты 3x3	2026-01-27 02:26:53.341263
113	5245484303	5245484303	SLOT_GAME	5	Казино: Слоты 3x3	2026-01-27 02:31:40.526615
114	5245484303	5245484303	SLOT_GAME	5	Казино: Слоты 3x3	2026-01-27 02:31:48.037566
115	5245484303	5245484303	SLOT_GAME	4	Казино: Слоты 3x3	2026-01-27 02:31:52.74566
116	5245484303	5245484303	SLOT_GAME	26	Казино: Слоты 3x3	2026-01-27 02:31:57.200713
117	5245484303	5245484303	SLOT_GAME	-5	Казино: Слоты 3x3	2026-01-27 02:32:03.215259
118	5245484303	5245484303	SLOT_GAME	5	Казино: Слоты 3x3	2026-01-27 02:32:07.765494
119	5245484303	5245484303	SLOT_GAME	-5	Казино: Слоты 3x3	2026-01-27 02:35:26.144459
120	5245484303	5245484303	SLOT_GAME	-5	Казино: Слоты 3x3	2026-01-27 02:35:30.343194
121	5245484303	5245484303	SLOT_GAME	-5	Казино: Слоты 3x3	2026-01-27 02:35:35.456751
122	5245484303	5245484303	SLOT_GAME	-5	Казино: Слоты 3x3	2026-01-27 02:36:06.536281
123	5245484303	5245484303	SLOT_GAME	15	Казино: Слоты 3x3	2026-01-27 02:36:10.666717
124	5245484303	5245484303	SLOT_GAME	3	Казино: Слоты 3x3	2026-01-27 02:36:25.021235
125	5245484303	5245484303	SLOT_GAME	20	Казино: Слоты 3x3	2026-01-27 02:36:29.796395
126	5245484303	5245484303	SLOT_GAME	-5	Казино: Слоты 3x3	2026-01-27 02:36:51.855401
127	5245484303	5245484303	SLOT_GAME	180	Казино: Слоты 3x3	2026-01-27 02:37:03.299191
128	5245484303	5245484303	SLOT_GAME	97	Казино: Слоты 3x3	2026-01-27 02:38:06.369264
129	5245484303	5245484303	SLOT_GAME	-5	Казино: Слоты 3x3	2026-01-27 02:39:17.708255
130	5245484303	5245484303	SLOT_GAME	36	Казино: Слоты 3x3	2026-01-27 02:39:21.862881
131	5245484303	5245484303	SLOT_GAME	10	Казино: Слоты 3x3	2026-01-27 02:39:40.367355
132	5245484303	5245484303	SLOT_GAME	2	Казино: Слоты 3x3	2026-01-27 02:40:17.318161
133	5245484303	5245484303	SLOT_GAME	355	Казино: Слоты 3x3	2026-01-27 02:43:07.006367
134	5245484303	5245484303	SLOT_GAME	-300	Казино: Слоты 3x3	2026-01-27 02:45:06.11285
135	5245484303	5245484303	SLOT_GAME	-50	Казино: Слоты 3x3	2026-01-27 02:45:13.629333
136	5245484303	5245484303	SLOT_GAME	6	Казино: Слоты 3x3	2026-01-27 02:46:00.891626
137	5245484303	5245484303	SLOT_GAME	10	Казино: Слоты 3x3	2026-01-27 02:46:21.465258
138	5245484303	5245484303	SLOT_GAME	10	Казино: Слоты 3x3	2026-01-27 02:46:28.182816
139	5245484303	5245484303	SLOT_GAME	6	Казино: Слоты 3x3	2026-01-27 02:46:36.503138
140	5245484303	5245484303	SLOT_GAME	8	Казино: Слоты 3x3	2026-01-27 04:03:15.118969
141	5245484303	5245484303	SLOT_GAME	12	Казино: Слоты 3x3	2026-01-27 04:03:26.723779
142	5245484303	5245484303	SLOT_GAME	6	Казино: Слоты 3x3	2026-01-27 04:03:32.679423
143	5245484303	5245484303	SLOT_GAME	-15	Казино: Слоты 3x3	2026-01-27 04:03:36.642808
144	5245484303	5245484303	CASINO_GAME	10	Казино: Слоты	2026-01-27 04:06:06.275248
145	5245484303	5245484303	admin_give	150000000	Без причины	2026-01-27 04:06:36.084759
146	5245484303	5245484303	CASINO_GAME	187500016	Казино: Слоты	2026-01-27 04:06:46.845265
147	5245484303	5245484303	CASINO_GAME	93750008	Казино: Слоты	2026-01-27 04:06:53.958263
148	5245484303	5245484303	CASINO_GAME	117187510	Казино: Слоты	2026-01-27 04:07:01.226233
149	5245484303	5245484303	CASINO_GAME	58593755	Казино: Слоты	2026-01-27 04:07:08.656173
150	5245484303	5245484303	CASINO_GAME	29296877	Казино: Слоты	2026-01-27 04:07:17.287269
151	5245484303	5245484303	CASINO_GAME	58593754	Казино: Слоты	2026-01-27 04:07:34.909195
152	5245484303	5245484303	CASINO_GAME	70312504	Казино: Слоты	2026-01-27 04:17:58.609197
153	5245484303	5245484303	CASINO_GAME	28125001	Казино: Слоты	2026-01-27 04:18:19.599269
154	5245484303	5245484303	CASINO_GAME	-28125001	Казино: Слоты	2026-01-27 04:18:37.828177
\.


--
-- Data for Name: meme_countries; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.meme_countries (country_id, ruler_id, chat_id, name, memename, description, ideology, avatar_url, "position", map_url, influence_points, avg_rating, total_reviews, tax_rate, treasury, flag_file_id, map_file_id, created_at, country_url) FROM stdin;
5	1180169608	-1003402767697	атао	коты	Описание не предоставлено.	Социализм	\N	Путешественник	\N	0	0	0	0	0	\N	\N	2026-01-22 03:58:28.216803	\N
6	1615370176	-1002799425221	РК Шварценбляхерштадт	Киров	Описание не предоставлено.	Национал-коммунизм	AQADAgADjhFrGyhviEoACAMAAzsZf4QW____IP4Ib6Z8lX04BA	Путешественник	\N	0	0	0	0	0	\N	\N	2026-01-22 03:58:28.216803	\N
7	837028648	-1003581340447	Тест	Биб младший	Описание не предоставлено.	Социализм	\N	Путешественник	\N	0	0	0	0	0	\N	\N	2026-01-22 03:58:28.216803	\N
3	5245484303	-1001722527791	◼️Аторния◼️	AceAttorney	хуй	ДЕМОКРАТИЯ raaaaaaah🦅🦅🦅🦅🦅	AQADAgAD3PkxG7JwmEkACAMAA9E_r8QW____CDEmh8Ww3-Y4BA	Путешественник	\N	0	5	2	0	0	\N	\N	2026-01-22 03:58:28.216803	https://t.me/+TBsgg37s3NE0MGJi
4	6262100430	-1003390594330	Υπερβόρειο Χετμανάτο	Гиперборея + Агарта	Описание не предоставлено.	Национализм	AQADAgADZwxrG0g3iUkACAMAA-aSQmEW____WQcd6LS4MsQ4BA	Путешественник	\N	0	4	1	0	0	\N	\N	2026-01-22 03:58:28.216803	\N
\.


--
-- Data for Name: punishments; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.punishments (id, user_id, admin_id, action_type, reason, created_at, expires_at, is_active) FROM stdin;
1	8451399261	5245484303	COUNTRY_CREATION_BAN	Без причины	2025-12-30 14:57:15.420162	\N	t
2	6777326894	5245484303	COUNTRY_CREATION_BAN	Без причины	2026-01-01 14:11:24.934762	\N	t
\.


--
-- Data for Name: reserved_country_names; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.reserved_country_names (id, name, added_by, added_at) FROM stdin;
\.


--
-- Data for Name: rp_events; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.rp_events (event_id, admin_id, chat_id, title, description, status, created_at, finished_at) FROM stdin;
1	5245484303	-1001722527791	ИГРТАЕМ в КАЗИНО	отыгрываем игру в казик тип продаём душу матери порнольва в слоты	finished	2026-01-24 19:13:44.500915	2026-01-24 20:27:53.511563
3	6262100430	-1003390594330	Авария	на АЭС в Адамовске	finished	2026-01-24 20:34:06.656062	2026-01-24 20:57:07.489581
4	6262100430	-1003390594330	Тема:инопланетяне	крестоносцы высаживаются на Землю	active	2026-01-24 20:57:14.107404	\N
2	5245484303	-1001722527791	УБЕЙ ЖИРНОГО ОТЧИМА С ПЕТАРДАМИ В ЖОПЕ	попробуй убить жирдяя который буквально каждую твою атаку сносит своим хуем	finished	2026-01-24 20:32:38.48862	2026-01-24 21:42:18.889243
5	6051072463	-1001722527791	betamemeworld_bot	"Восстание отпетушиных фембоев"\n\nЖенщины вымерли и люди начали ебать фембоев фембои заебались и подняли восстание\nСкоро второе пришествие матери Габена.....\n\n-10	finished	2026-01-24 23:58:07.703779	2026-01-25 15:53:38.118623
6	5245484303	-1001722527791	11 сентября	отыгрываем 11 сентября нужны пилоты и террористы	finished	2026-01-25 15:55:09.597081	2026-01-25 16:32:18.196672
\.


--
-- Data for Name: rp_participants; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.rp_participants (participant_id, event_id, user_id, joined_at) FROM stdin;
1	1	5245484303	2026-01-24 19:15:57.68762
2	1	5922612105	2026-01-24 19:52:15.042713
3	1	6243057226	2026-01-24 19:52:26.325219
4	2	6243057226	2026-01-24 20:32:58.005883
5	2	6893332028	2026-01-24 20:33:13.769767
6	3	6262100430	2026-01-24 20:34:33.828575
7	3	6243057226	2026-01-24 20:34:38.178394
8	3	5525767745	2026-01-24 20:34:42.646835
9	3	8183676732	2026-01-24 20:36:08.666053
10	4	8183676732	2026-01-24 20:57:15.80299
11	4	6262100430	2026-01-24 20:57:16.399004
12	4	5525767745	2026-01-24 20:57:28.047339
13	4	8437850340	2026-01-24 20:58:07.801173
14	5	6893332028	2026-01-24 23:58:30.991906
15	5	6262100430	2026-01-25 00:04:48.168981
16	5	5188135081	2026-01-25 15:06:29.454083
17	6	6051072463	2026-01-25 15:55:18.310956
19	6	992392675	2026-01-25 15:56:31.086698
21	6	6243057226	2026-01-25 15:59:30.231688
22	6	5245484303	2026-01-25 15:59:58.335802
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: Ya1chko
--

COPY public.users (user_id, userfullname, username, points, "position", is_ruler, last_country_creation, last_country_deletion, adminlevel, country_id, lost_in_casino) FROM stdin;
6957483151	EMELYA	sock_of_fate_official	0	Путешественник	f	\N	\N	0	\N	0
936962126	Sergey Aleksandrovich	MR_0_0_EL	0	Путешественник	f	\N	\N	0	\N	0
7886587133	R	Raararrrrr	0	Путешественник	f	\N	\N	0	\N	0
6168229448	Парадокс Онлайна	paradoksonlayna	0	Путешественник	f	\N	\N	0	\N	0
1689329449	Limbo		5	Путешественник	f	\N	\N	0	\N	0
8047373961	𝕶𝖚𝖗𝖔𝖘𝖆𝖜𝖆 𝕹𝖆𝖔𝖙𝖔	Sugar_Apple_Fairy_Tale2	0	Путешественник	f	\N	\N	0	\N	0
7176038937	sh4rkune	lap4si0n	0	Путешественник	f	\N	\N	0	\N	0
6262100430	.		20	Правитель	t	2026-01-02 12:25:38.658587	\N	0	4	0
7806400455	Его курфюрстская светлость, Фридрих Август I, Божьей милостью:	lJustWannaAlive	0	Путешественник	f	\N	\N	0	\N	0
5211933622	Cumрад🇷🇺	Abyga1	0	Путешественник	f	\N	\N	0	\N	0
5249448165	𝔅𝔒𝔇ℜℑℭℌ	OWDliberal	0	Путешественник	f	\N	\N	0	\N	0
8222821146	StalInoyStall	StalnoyStall	0	Путешественник	f	\N	\N	0	\N	0
6259399516	𝐯𝐢𝐭𝐨	vito_kmr	0	Путешественник	f	\N	\N	0	\N	0
8081867987	kraims	wocrimes	0	Путешественник	f	\N	\N	0	\N	0
7213516876	Player2008	\N	0	Путешественник	f	\N	\N	0	\N	0
5940645904	Давид	Gabork1	0	Путешественник	f	\N	\N	0	\N	0
5245484303	☾︎Y͜͡ă̈|c̥ͦh͜͡k̑̈o͜͡☽︎ 👼🏿🎸⁴²	Ya1chko	0	Правитель	t	2026-01-02 11:58:58.092256	\N	0	3	28125016
1563715232	Некрон	Necron2100	0	Путешественник	f	\N	\N	0	\N	0
7373948671	🅉 | Пират P░v	iminBrussel	0	Путешественник	f	\N	\N	0	\N	0
8451399261	Vadim Слива	Vadimsliva	0	Путешественник	f	\N	\N	0	\N	0
1615370176	Иван Устинов	IvanUstinov67	10	Правитель	t	2026-01-02 14:54:29.130247	\N	0	6	0
6777326894	TEST	Testya1chkoBot	15	Путешественник	f	\N	\N	0	\N	0
1625137625	Негро Желе	Nothabibinotc4	0	Гражданин	f	\N	\N	0	3	0
8541415397	David 🇦🇲🇺🇸	Armenian_DNI	0	Путешественник	f	\N	\N	0	\N	0
5139558597	Negus Negesti	SANGELIEVICH	0	Гражданин	f	\N	\N	0	6	0
792295258	Ds	Dan_its_me	0	Путешественник	f	\N	\N	0	\N	0
8510482793	💀💀💀	UraUrfak	0	Путешественник	f	\N	\N	0	\N	0
2111881608	.	Javier_Gerardo_Milei	0	Путешественник	f	\N	\N	0	\N	0
1735359418	𝓼𝓪𝓷𝓮𝓬𝓱𝓴𝓪	chaYnbly	0	Гражданин	f	\N	\N	0	3	0
1202482849	⁴Nexul²	datayo	0	Гражданин	f	\N	\N	0	3	0
2099359849	YDT	General_Piva	0	Путешественник	f	\N	\N	0	\N	0
6112246286	Тимоха	Myjdjx	0	Путешественник	f	\N	\N	0	\N	0
1095847863	Дэн Сяопин	Minecraftismlife	0	Путешественник	f	\N	\N	0	\N	0
1352804932	⁴²𝙻𝚒𝚍𝚘𝚌𝚊𝚒𝚗𝚎	CaineDude42	0	Путешественник	f	\N	\N	0	\N	0
5803699777	ᗜ⩊ᗜ CHIKIT ᗜ⩊ᗜ	chik_kit	0	Путешественник	f	\N	\N	0	\N	0
5007147634	~morozko	salovya	0	Путешественник	f	\N	\N	0	\N	0
6045713401	Авраам Револьц	Vjk600	0	Гражданин	f	\N	\N	0	4	0
5742270445	ВоваСиб ❅	Veva_Lifi	0	Гражданин	f	\N	\N	0	4	0
1854987620	⁴²Недосып Подмефедронедосырович⁴²	Mistakyn	0	Путешественник	f	\N	\N	0	\N	0
6254291755	Sus	Lyti_pon5	0	Путешественник	f	\N	\N	0	\N	0
6265630174	ᅠ • 𝚢𝚊𝚋𝚘𝚔𝚞	Ppponnp	0	ГЕРОЙ	f	\N	\N	0	3	0
8552036745	Волзер Лемонов 🍍<Вацар> [мнж] [пвканон] -👔🪆- ^щб^ ?вайбер¿ «вазелин»	walz0	0	Гражданин	f	\N	\N	0	4	0
5667570277	«A N D R E W»	L_P_R_R_U_S	0	вице-премьер	f	\N	\N	0	4	0
6513250501	👾Калуга☭⃠ Смысловский_Avdeev 4ever🇷🇺 ☦️📿	Kaluga_anannas	0	Гражданин	f	\N	\N	0	4	0
6608663108	ℝ𝕦𝕝𝕖𝕣 𝕆𝕗 𝔼𝕧𝕖𝕣𝕪𝕥𝕙𝕚𝕟𝕘	Unreggcognizable	0	Гражданин	f	\N	\N	0	3	0
5703010572	Lilly 🍓		0	Путешественник	f	\N	\N	0	\N	0
1905241494	Rayz | Копирайтер	ruswallstreet	0	Путешественник	f	\N	\N	0	\N	0
1669070521	Никита	RussianFreethinker	0	Путешественник	f	\N	\N	0	\N	0
6283690984	011	mr011022011	15	Гражданин	f	\N	\N	0	3	0
6631566083	Горящие Помойки	Goryshiy	0	Путешественник	f	\N	\N	0	\N	0
977008008	iriss	iriss_rotaleno	0	Путешественник	f	\N	\N	0	\N	0
6001376284	Amnam	Amnam_pups	0	Гражданин	f	\N	\N	0	4	0
8103972141	[💣] Whittmor Filizankovič[💣]		0	Путешественник	f	\N	\N	0	\N	0
5141159866	Timoty🪽(he/his)	TimotyStarlight	0	Путешественник	f	\N	\N	0	\N	0
6602534683	𝓐𝓻𝓽 𝓝𝓮𝓻𝓿 | 𝓒𝓸𝓷𝓼𝓮𝓻𝓿𝓪𝓽𝓲𝓼𝓶	Dr_art6	0	Путешественник	f	\N	\N	0	\N	0
1180169608	🐽ron!🐽	pidrosfera	0	Правитель	t	2026-01-02 12:37:14.368839	\N	0	5	0
6583782673	bigmak倉庫可 Stars 1.32 онлайн	bigmak_nft	0	Путешественник	f	\N	\N	0	\N	0
8498559832	Олег Гитлер	AdolfKlitor123	0	Гражданин	f	\N	\N	0	4	0
632980846	𝚕𝚊𝚕𝚘 𝚜𝚊𝚕𝚊𝚖𝚊𝚗𝚌𝚊	\N	0	Путешественник	f	\N	\N	0	\N	0
661190030	Новогодний друн	\N	0	Путешественник	f	\N	\N	0	\N	0
8262902147	𝑪𝒍𝒆𝒐𝑿 🇺🇲	cleoxx25	0	Путешественник	f	\N	\N	0	\N	0
5344510663	-_EDMOND_-	Edmond00	0	Путешественник	f	\N	\N	0	\N	0
8477587907	Nikolas Maduro (Official)	FreeMaduros	0	Путешественник	f	\N	\N	0	\N	0
8119431286	@распятие🗿	raspyatie17	0	Путешественник	f	\N	\N	0	\N	0
5922612105	Ergeus	Ergeus	10	Гражданин	f	\N	\N	0	3	0
6354520423	Vovan د.ك	Kwintillion574ivovan198	0	Путешественник	f	\N	\N	0	\N	0
777000	Telegram		0	Путешественник	f	\N	\N	0	\N	0
6243057226	Арсений Барсук	Arwutp	40	Путешественник	f	\N	\N	0	\N	0
8183676732	Хосров II Парвиз	markvetokhin	10	Гражданин	f	\N	\N	0	4	0
1996901470	[ɪʙᴜ] каша	IBUQI	0	Гражданин	f	\N	\N	0	3	0
6893332028	Ликси/Лао De foxies	St4nikLik	20	Гражданин	f	\N	\N	0	3	0
8437850340	Please enter your name	sexy_girl_wants_sex	0	Путешественник	f	\N	\N	0	\N	0
7494375941	Пон	hjjjiiil	0	Путешественник	f	\N	\N	0	\N	0
837028648	Биб Бон ,картограф БНА	Bib_bon	10	Правитель	t	2026-01-05 15:10:41.036982	\N	0	7	0
8505485423	Walzer Lemonov	walz0	10	Бывший правитель империи	f	2026-01-05 15:17:52.254617	\N	0	\N	0
1159195257	машша шайн(⁠✿⁠^⁠‿⁠^⁠)	mshashine	0	Путешественник	f	\N	\N	0	\N	0
1242059436	ㅤ	\N	0	Путешественник	f	\N	\N	0	\N	0
7243120686	mephedronic	YMEPAET_B_MYKAX_ADA	0	Путешественник	f	\N	\N	0	\N	0
6384121136	lesha	bebr1aw	0	Путешественник	f	\N	\N	0	\N	0
1900245819	𝔚𝔢𝔩⸸𝔰𝔠𝔥𝔪𝔢𝔯𝔷 𝄞 #407 #WS #DSBM	weltschmerzWs	0	Путешественник	f	\N	\N	0	\N	0
5526348530	волна летнего шампуня	Pilonqwerty	0	Путешественник	f	\N	\N	0	\N	0
5299817303	Денис	Denis45go	0	Путешественник	f	\N	\N	0	\N	0
5726456353	ℭ𝔥𝔢𝔩𝔣	chelf	0	Путешественник	f	\N	\N	0	\N	0
5372350673	Г🇫🇮🥋	fin333333	0	Путешественник	f	\N	\N	0	\N	0
1768612944	ঔৣ☬✞𝐹𝑒𝓃𝒹𝑒𝓇 & 𝒜𝓇𝓅𝒽𝑒𝓎✞☬ঔৣ	TheManWithThePlan_C0Lter	0	Путешественник	f	\N	\N	0	\N	0
6870198083	ㅤ꧁༒⫷𝑹𝑶𝑺𝑺𝑰𝑶𝑵789✧⎠⎠╾━╤デ╦︻	rossion_WoT	0	Путешественник	f	\N	\N	0	\N	0
6569561020	𐍃𐍔𐍃𐌕𐌅	Systf	0	Путешественник	f	\N	\N	0	\N	0
7198803642	Артем Казначеев 🇷🇺🇪🇺	WalkisTT	0	Путешественник	f	\N	\N	0	\N	0
5371568929	🇬🇮Xilka⚪🔵⚫	Xilka322	0	Путешественник	f	\N	\N	0	\N	0
5369740752	Nik	Straz7	0	Путешественник	f	\N	\N	0	\N	0
5398564150	Шеф Архангелецъ [𖢖]	Stydentov	0	Путешественник	f	\N	\N	0	\N	0
1858628439	ᅠ ︎ ︎ ︎ ︎ ᅠ ︎ ︎ ︎ ︎ ᅠ ︎	kaiju8766	0	Путешественник	f	\N	\N	0	\N	0
5670863515	Veltiх	\N	0	Путешественник	f	\N	\N	0	\N	0
5331121857	Бёрн фон Серафау	srph_burning_one	0	Путешественник	f	\N	\N	0	\N	0
7379059025	Точка м	weftcg	0	Путешественник	f	\N	\N	0	\N	0
7218144465	Chuchundra	Chundrr	0	Путешественник	f	\N	\N	0	\N	0
1215605020	🇨🇿 Чехия 🇨🇿	Czech_Republic228	0	Путешественник	f	\N	\N	0	\N	0
5423248430	умни типок	Ninjagolover	0	Путешественник	f	\N	\N	0	\N	0
8162145918	альп альпо	alp_alpo	0	Путешественник	f	\N	\N	0	\N	0
5318645943	Chill Taco	ChillTakoBell	0	Путешественник	f	\N	\N	0	\N	0
7103274533	.	onmoduls	0	Гражданин	f	\N	\N	0	3	0
6579378446	Миха Бро	MibroZxc	0	Путешественник	f	\N	\N	0	\N	0
5525767745	Робеспьер Максимилиан	ignoringmycalling	10	Путешественник	f	\N	\N	0	\N	0
8226387796	Adolf Hitler	FuehrerAdolf	0	Путешественник	f	\N	\N	0	\N	0
8538790825	slatt	slattyq	0	Путешественник	f	\N	\N	0	\N	0
7488500620	Sluplot		0	Путешественник	f	\N	\N	0	\N	0
1176115795	Vova	Sswjbt	0	Путешественник	f	\N	\N	0	\N	0
6411580028	ㅤ	pacchesun	0	Путешественник	f	\N	\N	0	\N	0
6426308405	ㅤ	Skskelek	0	Путешественник	f	\N	\N	0	\N	0
2117369943	Андрей	SinXZT	0	Путешественник	f	\N	\N	0	\N	0
5188135081	Назар 当	V1blue	10	Путешественник	f	\N	\N	0	\N	0
992392675	Aleks Rababyi	Lolkabiba	10	Путешественник	f	\N	\N	0	\N	0
6051072463	William (Springtrump)	Mrbebra123455	10	Путешественник	f	\N	\N	0	\N	0
2059599054	рита	qwqgus	0	Путешественник	f	\N	\N	0	\N	0
1600990916	🐡|ⱫłⱤⱤØ🩸⃠	ZirroOfDeath	0	Путешественник	f	\N	\N	0	\N	0
5130129736	#deko#мелстрой помс он обляко (прізідінт острова мЭна🇮🇲	MC_apple_but_pug	0	Путешественник	f	\N	\N	0	\N	0
5063836686	Velikiy Finn🇫🇮	Velikiy_finn	0	Путешественник	f	\N	\N	0	\N	0
1409811047	Hahol	Pizdets222888	0	Путешественник	f	\N	\N	0	\N	0
6888162660	AuraVitas	ClownPierce13	0	Путешественник	f	\N	\N	0	\N	0
8520739067	Зтогг Сэнна	Ztogg_Senna	0	Путешественник	f	\N	\N	0	\N	0
7434621212	ㅤ‎		0	Путешественник	f	\N	\N	0	\N	0
924296512	miracle		186	Гражданин	f	\N	\N	0	3	0
8567623952	†Пауль Йозеф Геббельс†	MichailMGE	0	Путешественник	f	\N	\N	0	\N	0
7061149540	▐⧯]ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ⃝ᡃ		0	Путешественник	f	\N	\N	0	\N	0
1165712496	jzrd		0	Путешественник	f	\N	\N	0	\N	0
\.


--
-- Name: country_blacklist_id_seq; Type: SEQUENCE SET; Schema: public; Owner: Ya1chko
--

SELECT pg_catalog.setval('public.country_blacklist_id_seq', 1, false);


--
-- Name: country_reviews_review_id_seq; Type: SEQUENCE SET; Schema: public; Owner: Ya1chko
--

SELECT pg_catalog.setval('public.country_reviews_review_id_seq', 5, true);


--
-- Name: history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: Ya1chko
--

SELECT pg_catalog.setval('public.history_id_seq', 154, true);


--
-- Name: meme_countries_country_id_seq; Type: SEQUENCE SET; Schema: public; Owner: Ya1chko
--

SELECT pg_catalog.setval('public.meme_countries_country_id_seq', 8, true);


--
-- Name: punishments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: Ya1chko
--

SELECT pg_catalog.setval('public.punishments_id_seq', 2, true);


--
-- Name: reserved_country_names_id_seq; Type: SEQUENCE SET; Schema: public; Owner: Ya1chko
--

SELECT pg_catalog.setval('public.reserved_country_names_id_seq', 1, false);


--
-- Name: rp_events_event_id_seq; Type: SEQUENCE SET; Schema: public; Owner: Ya1chko
--

SELECT pg_catalog.setval('public.rp_events_event_id_seq', 6, true);


--
-- Name: rp_participants_participant_id_seq; Type: SEQUENCE SET; Schema: public; Owner: Ya1chko
--

SELECT pg_catalog.setval('public.rp_participants_participant_id_seq', 22, true);


--
-- Name: users_user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: Ya1chko
--

SELECT pg_catalog.setval('public.users_user_id_seq', 1, false);


--
-- Name: country_reviews _user_country_uc; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_reviews
    ADD CONSTRAINT _user_country_uc UNIQUE (user_id, country_id);


--
-- Name: admins admins_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_pkey PRIMARY KEY (user_id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: country_blacklist country_blacklist_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_blacklist
    ADD CONSTRAINT country_blacklist_pkey PRIMARY KEY (id);


--
-- Name: country_reviews country_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_reviews
    ADD CONSTRAINT country_reviews_pkey PRIMARY KEY (review_id);


--
-- Name: history history_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.history
    ADD CONSTRAINT history_pkey PRIMARY KEY (id);


--
-- Name: meme_countries meme_countries_chat_id_key; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.meme_countries
    ADD CONSTRAINT meme_countries_chat_id_key UNIQUE (chat_id);


--
-- Name: meme_countries meme_countries_memename_key; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.meme_countries
    ADD CONSTRAINT meme_countries_memename_key UNIQUE (memename);


--
-- Name: meme_countries meme_countries_name_key; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.meme_countries
    ADD CONSTRAINT meme_countries_name_key UNIQUE (name);


--
-- Name: meme_countries meme_countries_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.meme_countries
    ADD CONSTRAINT meme_countries_pkey PRIMARY KEY (country_id);


--
-- Name: punishments punishments_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.punishments
    ADD CONSTRAINT punishments_pkey PRIMARY KEY (id);


--
-- Name: reserved_country_names reserved_country_names_name_key; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.reserved_country_names
    ADD CONSTRAINT reserved_country_names_name_key UNIQUE (name);


--
-- Name: reserved_country_names reserved_country_names_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.reserved_country_names
    ADD CONSTRAINT reserved_country_names_pkey PRIMARY KEY (id);


--
-- Name: rp_events rp_events_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.rp_events
    ADD CONSTRAINT rp_events_pkey PRIMARY KEY (event_id);


--
-- Name: rp_participants rp_participants_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.rp_participants
    ADD CONSTRAINT rp_participants_pkey PRIMARY KEY (participant_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: ix_country_blacklist_country_id; Type: INDEX; Schema: public; Owner: Ya1chko
--

CREATE INDEX ix_country_blacklist_country_id ON public.country_blacklist USING btree (country_id);


--
-- Name: ix_country_blacklist_id; Type: INDEX; Schema: public; Owner: Ya1chko
--

CREATE INDEX ix_country_blacklist_id ON public.country_blacklist USING btree (id);


--
-- Name: ix_history_admin_time; Type: INDEX; Schema: public; Owner: Ya1chko
--

CREATE INDEX ix_history_admin_time ON public.history USING btree (admin_id, "timestamp");


--
-- Name: ix_history_event_type; Type: INDEX; Schema: public; Owner: Ya1chko
--

CREATE INDEX ix_history_event_type ON public.history USING btree (event_type);


--
-- Name: ix_history_target_time; Type: INDEX; Schema: public; Owner: Ya1chko
--

CREATE INDEX ix_history_target_time ON public.history USING btree (target_id, "timestamp");


--
-- Name: ix_punishments_id; Type: INDEX; Schema: public; Owner: Ya1chko
--

CREATE INDEX ix_punishments_id ON public.punishments USING btree (id);


--
-- Name: ix_punishments_user_id; Type: INDEX; Schema: public; Owner: Ya1chko
--

CREATE INDEX ix_punishments_user_id ON public.punishments USING btree (user_id);


--
-- Name: admins admins_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: country_blacklist country_blacklist_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_blacklist
    ADD CONSTRAINT country_blacklist_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.users(user_id);


--
-- Name: country_blacklist country_blacklist_country_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_blacklist
    ADD CONSTRAINT country_blacklist_country_id_fkey FOREIGN KEY (country_id) REFERENCES public.meme_countries(country_id);


--
-- Name: country_blacklist country_blacklist_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_blacklist
    ADD CONSTRAINT country_blacklist_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: country_reviews country_reviews_country_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_reviews
    ADD CONSTRAINT country_reviews_country_id_fkey FOREIGN KEY (country_id) REFERENCES public.meme_countries(country_id);


--
-- Name: country_reviews country_reviews_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.country_reviews
    ADD CONSTRAINT country_reviews_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: history history_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.history
    ADD CONSTRAINT history_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.users(user_id);


--
-- Name: history history_target_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.history
    ADD CONSTRAINT history_target_id_fkey FOREIGN KEY (target_id) REFERENCES public.users(user_id);


--
-- Name: meme_countries meme_countries_ruler_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.meme_countries
    ADD CONSTRAINT meme_countries_ruler_id_fkey FOREIGN KEY (ruler_id) REFERENCES public.users(user_id);


--
-- Name: punishments punishments_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.punishments
    ADD CONSTRAINT punishments_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.users(user_id);


--
-- Name: punishments punishments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.punishments
    ADD CONSTRAINT punishments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: reserved_country_names reserved_country_names_added_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.reserved_country_names
    ADD CONSTRAINT reserved_country_names_added_by_fkey FOREIGN KEY (added_by) REFERENCES public.users(user_id);


--
-- Name: rp_events rp_events_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.rp_events
    ADD CONSTRAINT rp_events_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.users(user_id);


--
-- Name: rp_participants rp_participants_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.rp_participants
    ADD CONSTRAINT rp_participants_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.rp_events(event_id);


--
-- Name: rp_participants rp_participants_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.rp_participants
    ADD CONSTRAINT rp_participants_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: users users_country_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: Ya1chko
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_country_id_fkey FOREIGN KEY (country_id) REFERENCES public.meme_countries(country_id);


--
-- PostgreSQL database dump complete
--

\unrestrict bnrcw0Iu433GAE8oYS0XvwEgqlnfKQiGBWSsKAjbD9VavYDj9IjLkSUs1rCO01x

