// Mirrors the Python API (src/mtgcv/analyze.py CardInfo / Report.to_api_dict, server.py).

export interface Card {
  key: string; // "<section>:<name>" — unique within a deck
  name: string;
  quantity: number;
  section: string;
  found: boolean;
  scryfall_id: string | null;
  oracle_id: string | null;
  mana_cost: string;
  cmc: number;
  type_line: string;
  main_type: string;
  layout: string;
  oracle_text: string;
  power: string | null;
  toughness: string | null;
  loyalty: string | null;
  colors: string[];
  color_identity: string[];
  keywords: string[];
  rarity: string;
  set_code: string;
  set_name: string;
  collector_number: string;
  edhrec_rank: number | null;
  game_changer: boolean;
  commander_legal: boolean | null;
  price_usd: number | null;
  image_normal: string | null;
  image_small: string | null;
  image_art_crop: string | null;
  image_back: string | null;
  scryfall_uri: string | null;
  edhrec_uri: string | null;
  tags: string[];
  strong_tags: string[];
  categories: string[];
  primary_category: string;
  user_tags: string[];
}

export interface Summary {
  total_cards: number;
  unique_cards: number;
  not_found: number;
  lands: number;
  average_cmc_nonland: number;
  color_identity: string[];
  median_edhrec_rank: number | null;
  game_changers: string[];
  total_price_usd: number;
  category_counts: Record<string, number>;
}

export interface GroupRef {
  name: string;
  cards: string[]; // card keys
}

export interface Report {
  summary: Summary;
  cards: Card[];
  groupings: Record<GroupMode, GroupRef[]>;
  not_found: string[];
  parse_errors: { line: number; text: string }[];
  tag_descriptions: Record<string, string>;
}

export interface DeckSummary {
  id: number;
  name: string;
  card_count: number;
  created_at: number;
  updated_at: number;
}

export interface BoardGroup {
  id: string;
  name: string;
  cards: string[];
}

export interface BoardLayout {
  groups: BoardGroup[];
}

export interface Board {
  id: number;
  deck_id: number;
  name: string;
  layout: BoardLayout;
  created_at: number;
  updated_at: number;
}

export interface DeckDetail {
  deck: DeckSummary & { text: string };
  report: Report;
  boards: Board[];
}

export type GroupMode = 'category' | 'primary' | 'type' | 'cmc' | 'color' | 'section' | 'user_tag' | 'none';
export type SeedMode = 'primary' | 'type' | 'cmc' | 'color' | 'section' | 'user_tag' | 'empty';
export type SortBy = 'edhrec' | 'name' | 'cmc' | 'price';
/** src/mtgcv/importers.py ImportResult */
export interface ImportResult {
  text: string;
  rows: number;
  cards: number;
  unique: number;
  skipped_tokens: number;
  skipped_lists: number;
  errors: string[];
}

export type ViewMode ='board' | 'table' | 'grid' | 'graph';

// --- synergy graph (src/mtgcv/synergy.py Graph.to_dict, server.py /graph) ---
export type GraphMode = 'tags' | 'edhrec' | 'lift';

export interface GraphData {
  mode: GraphMode;
  nodes: string[]; // card keys
  hubs: string[]; // commander card keys (edhrec / lift modes)
  edges: [number, number, number, number][]; // [sourceIdx, targetIdx, rawWeight, labelIdx | -1]
  labels: string[];
  unconnected: number;
  meta: { themes?: string[]; commanders?: number; missing_pages?: string[] };
}

export type Positions = Record<string, [number, number]>;

export type GraphResponse =
  | { status: 'loading'; progress: { done: number; total: number } }
  | { status: 'ready'; graph: GraphData; layout: Positions | null };

/** src/mtgcv/synergy.py explain_pair() — why two cards synergize. */
export interface PairTheme {
  theme: string;
  payoff: string; // card key
  enabler: string; // card key
  payoff_reasons: string[];
  enabler_reasons: string[];
}

export interface PairEdhrec {
  commander: string; // card key
  card: string; // card key
  status: 'listed' | 'not_listed' | 'no_page' | 'not_downloaded';
  commander_decks?: number;
  synergy?: number;
  num_decks?: number;
  potential_decks?: number;
  lift?: number | null;
}

export interface PairExplanation {
  a: string;
  b: string;
  themes: PairTheme[];
  edhrec: PairEdhrec[] | null; // null = EDHREC graph modes disabled (features.py)
  shared_categories: string[];
  shared_tags: string[];
}

export interface Connection {
  key: string;
  label: string;
  weight: number; // raw
}

export const GROUP_LABELS: Record<GroupMode, string> = {
  category: 'Category (all)',
  primary: 'Primary category',
  type: 'Card type',
  cmc: 'Mana value',
  color: 'Color',
  section: 'List section',
  user_tag: 'Your tags',
  none: 'No grouping',
};

export const SORT_LABELS: Record<SortBy, string> = {
  edhrec: 'EDHREC rank',
  name: 'Name',
  cmc: 'Mana value',
  price: 'Price',
};

/** A group ready to render: resolved cards, plus whether it's a user-editable group. */
export interface ViewGroup {
  id: string;
  name: string;
  cards: Card[];
  editable: boolean;
}

export const UNSORTED_ID = '__unsorted';

// --- card filters (client-side; combine with the text search) ---
export type ColorMode = 'within' | 'any' | 'exact';

export interface Filters {
  colors: string[]; // 'W' | 'U' | 'B' | 'R' | 'G' | 'C'
  colorMode: ColorMode;
  types: string[]; // front-face type words: Creature, Instant, ...
  categories: string[];
  mvMin: number | null;
  mvMax: number | null;
  rankMax: number | null; // EDHREC rank <= this (unranked cards excluded)
  rarities: string[];
  priceMax: number | null; // cards without a price are kept
}

export const EMPTY_FILTERS: Filters = {
  colors: [],
  colorMode: 'within',
  types: [],
  categories: [],
  mvMin: null,
  mvMax: null,
  rankMax: null,
  rarities: [],
  priceMax: null,
};
