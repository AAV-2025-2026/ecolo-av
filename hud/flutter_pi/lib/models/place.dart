class Place {
  final int id;
  final String? name;
  final String? type;
  final String? houseNumber;
  final String? street;
  final String? city;
  final double lat;
  final double lon;

  Place({
    required this.id,
    required this.lat,
    required this.lon,
    this.name,
    this.type,
    this.houseNumber,
    this.street,
    this.city,
  });

  // Human readable display strings
  String get displayTitle {
    if (name != null) return name!;
    if (houseNumber != null && street != null) return '$houseNumber $street';
    if (street != null) return street!;
    return 'Unknown';
  }

  String get displaySubtitle {
    final parts = <String>[
      if (type != null) type!,
      if (street != null && name != null) street!,
      if (city != null) city!,
      '${lat.toStringAsFixed(5)}, ${lon.toStringAsFixed(5)}',
    ];
    return parts.join(' · ');
  }

  factory Place.fromMap(Map<String, dynamic> map) {
    return Place(
      id: map['id'] as int,
      name: map['name'] as String?,
      type: map['type'] as String?,
      houseNumber: map['house_number'] as String?,
      street: map['street'] as String?,
      city: map['city'] as String?,
      lat: (map['lat'] as num).toDouble(),
      lon: (map['lon'] as num).toDouble(),
    );
  }
}