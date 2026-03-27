// Auto-generated endpoint constants for Mnemo API v1
class Endpoints {
  static const String base = '/v1';

  // Health
  static const String health = '/v1/health';

  // Auth
  static const String authToken = '/v1/auth/token';

  // Users
  static const String users = '/v1/users';
  static String userById(String id) => '/v1/users/$id';

  // Countries
  static const String countries = '/v1/countries';
  static String countryByCode(String code) => '/v1/countries/$code';

  // Imports
  static const String imports = '/v1/imports';
  static String importById(String id) => '/v1/imports/$id';

  // Decks & cards
  static const String decks = '/v1/decks';
  static String deckById(String id) => '/v1/decks/$id';
  static String deckStats(String id) => '/v1/decks/$id/stats';

  static const String cards = '/v1/cards';
  static String cardById(String id) => '/v1/cards/$id';

  // Sessions
  static const String sessions = '/v1/sessions';
  static String sessionById(String id) => '/v1/sessions/$id';
  static String sessionAnswer(String id) => '/v1/sessions/$id/answer';
  static String sessionSkip(String id) => '/v1/sessions/$id/skip';
  static String sessionEnd(String id) => '/v1/sessions/$id/end';
  static String sessionSummary(String id) => '/v1/sessions/$id/summary';

  // Memory states, progress, plan
  static const String memoryStates = '/v1/memory-states';
  static const String progress = '/v1/progress';
  static const String plan = '/v1/plan';
}
