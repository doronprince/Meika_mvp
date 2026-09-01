import 'expense_category.dart';

enum StoreType {
  online,
  localSupermarket,
  traditionalMarket,
  convenienceStore;

  static StoreType fromJson(String value) {
    switch (value) {
      case 'online':
        return StoreType.online;
      case 'local_supermarket':
        return StoreType.localSupermarket;
      case 'traditional_market':
        return StoreType.traditionalMarket;
      case 'convenience_store':
        return StoreType.convenienceStore;
      default:
        return StoreType.online;
    }
  }

  String get displayName {
    switch (this) {
      case StoreType.online:
        return 'Online';
      case StoreType.localSupermarket:
        return 'Supermarket';
      case StoreType.traditionalMarket:
        return 'Traditional Market';
      case StoreType.convenienceStore:
        return 'Convenience Store';
    }
  }
}

enum PriceTrend {
  rising,
  falling,
  stable,
  insufficientData;

  static PriceTrend fromJson(String value) {
    switch (value) {
      case 'rising':
        return PriceTrend.rising;
      case 'falling':
        return PriceTrend.falling;
      case 'stable':
        return PriceTrend.stable;
      default:
        return PriceTrend.insufficientData;
    }
  }
}

class ClarityFactorLite {
  final String label;
  final String detail;

  const ClarityFactorLite({required this.label, required this.detail});

  factory ClarityFactorLite.fromJson(Map<String, dynamic> json) {
    return ClarityFactorLite(label: json['label'] as String, detail: json['detail'] as String);
  }
}

class StoreComparison {
  final String storeId;
  final String storeName;
  final StoreType storeType;
  final double priceKrw;
  final double transitCostKrw;
  final String transitMode;
  final double trueEconomicCostKrw;
  final PriceTrend priceTrend;
  final double rating;
  final bool inStock;
  final String? listingUrl;

  const StoreComparison({
    required this.storeId,
    required this.storeName,
    required this.storeType,
    required this.priceKrw,
    required this.transitCostKrw,
    required this.transitMode,
    required this.trueEconomicCostKrw,
    required this.priceTrend,
    required this.rating,
    required this.inStock,
    required this.listingUrl,
  });

  factory StoreComparison.fromJson(Map<String, dynamic> json) {
    return StoreComparison(
      storeId: json['store_id'] as String,
      storeName: json['store_name'] as String,
      storeType: StoreType.fromJson(json['store_type'] as String),
      priceKrw: parseAmount(json['price_krw']),
      transitCostKrw: parseAmount(json['transit_cost_krw']),
      transitMode: json['transit_mode'] as String,
      trueEconomicCostKrw: parseAmount(json['true_economic_cost_krw']),
      priceTrend: PriceTrend.fromJson(json['price_trend'] as String),
      rating: parseAmount(json['rating']),
      inStock: json['in_stock'] as bool,
      listingUrl: json['listing_url'] as String?,
    );
  }
}

class PriceFinderResult {
  final String productId;
  final String productName;
  final ExpenseCategory category;
  final List<StoreComparison> comparisons;
  final ClarityFactorLite recommendation;
  final bool isLive;

  const PriceFinderResult({
    required this.productId,
    required this.productName,
    required this.category,
    required this.comparisons,
    required this.recommendation,
    required this.isLive,
  });

  factory PriceFinderResult.fromJson(Map<String, dynamic> json) {
    return PriceFinderResult(
      productId: json['product_id'] as String,
      productName: json['product_name'] as String,
      category: ExpenseCategory.fromJson(json['category'] as String),
      comparisons: (json['comparisons'] as List)
          .map((c) => StoreComparison.fromJson(c as Map<String, dynamic>))
          .toList(),
      recommendation: ClarityFactorLite.fromJson(json['recommendation'] as Map<String, dynamic>),
      isLive: json['is_live'] as bool? ?? false,
    );
  }
}
