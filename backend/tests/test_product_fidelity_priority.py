from pathlib import Path
from unittest.mock import MagicMock

from app.ai.image.prompt_builder import (
    PROMPT_VERSION,
    _format_dimensions,
    build_design_generation_prompt,
)
from app.services.design_generation_service import (
    CATEGORY_REFERENCE_PRIORITY,
    DEFAULT_REFERENCE_PRIORITY,
    DesignGenerationService,
    get_category_reference_priority,
)


class DummyCategory:
    def __init__(self, name: str, slug: str):
        self.name = name
        self.slug = slug


class DummyAttribute:
    def __init__(self, name: str):
        self.name = name


class DummyProduct:
    def __init__(
        self,
        id: int,
        name: str,
        category_name: str,
        category_slug: str,
        price: float = 1000000.0,
        width: float | None = 80.0,
        height: float | None = 70.0,
        depth: float | None = 60.0,
        materials: list[str] | None = None,
        styles: list[str] | None = None,
        colors: list[str] | None = None,
        image_url: str | None = None,
    ):
        self.id = id
        self.name = name
        self.category = DummyCategory(category_name, category_slug)
        self.price = price
        self.width = width
        self.height = height
        self.depth = depth
        self.materials = [DummyAttribute(m) for m in (materials or ["Wood"])]
        self.styles = [DummyAttribute(s) for s in (styles or ["Modern"])]
        self.colors = [DummyAttribute(c) for c in (colors or ["Cream"])]
        self.images = []
        if image_url:
            mock_img = MagicMock()
            mock_img.image_url = image_url
            mock_img.is_primary = True
            mock_img.sort_order = 0
            self.images.append(mock_img)


def make_dummy_project():
    proj = MagicMock()
    proj.title = "Test Living Room"
    proj.room_type = "empty_room"
    proj.room_image_path = "1/1/source.jpg"
    return proj


def make_dummy_analysis():
    analysis = MagicMock()
    analysis.room_type = "empty_room"
    analysis.layout_summary = "An empty room with light hardwood flooring"
    analysis.empty_areas = [{"location": "center floor", "suitable_for_decor": True}]
    analysis.lighting = {"type": "natural light", "level": "bright"}
    return analysis


def make_dummy_preference():
    pref = MagicMock()
    pref.budget_min = 5000000
    pref.budget_max = 10000000
    pref.purpose = "Living"
    pref.styles = [DummyAttribute("Luxury")]
    pref.colors = [DummyAttribute("Cream")]
    pref.materials = [DummyAttribute("Wood")]
    pref.categories = []
    pref.notes = None
    return pref


def test_category_reference_priority_ranking():
    """Verify primary anchor furniture ranks higher than accents and lighting."""
    sofa = DummyProduct(1, "Sofa", "Sofa", "sofa")
    bedding = DummyProduct(2, "Bed", "Bedding", "bedding")
    storage = DummyProduct(3, "Wardrobe", "Storage", "storage")
    table = DummyProduct(4, "Dining Table", "Table", "table")
    chair = DummyProduct(5, "Chair", "Chair", "chair")
    rug = DummyProduct(6, "Rug", "Rug", "rug")
    lighting = DummyProduct(7, "Floor Lamp", "Lighting", "lighting")
    wall_decor = DummyProduct(8, "Mirror", "Wall Decor", "wall-decor")
    plant = DummyProduct(9, "Plant", "Plant Decor", "plant-decor")
    accessory = DummyProduct(10, "Cushion", "Accessories", "accessories")
    unknown = DummyProduct(11, "Misc", "Misc", "misc")

    assert get_category_reference_priority(sofa) == 10
    assert get_category_reference_priority(bedding) == 15
    assert get_category_reference_priority(storage) == 20
    assert get_category_reference_priority(table) == 30
    assert get_category_reference_priority(chair) == 40
    assert get_category_reference_priority(rug) == 50
    assert get_category_reference_priority(lighting) == 60
    assert get_category_reference_priority(wall_decor) == 70
    assert get_category_reference_priority(plant) == 80
    assert get_category_reference_priority(accessory) == 90
    assert get_category_reference_priority(unknown) == DEFAULT_REFERENCE_PRIORITY

    # Ascending order check
    items = [accessory, lighting, sofa, table, storage]
    sorted_items = sorted(items, key=get_category_reference_priority)
    assert [p.id for p in sorted_items] == [1, 3, 4, 7, 10]


def test_reference_priority_is_stable_for_same_category():
    """Verify Timsort stability preserves user order when products have same priority."""
    table1 = DummyProduct(6, "Glass Side Table", "Table", "table")
    table2 = DummyProduct(7, "Rattan Bedside Table", "Table", "table")
    table3 = DummyProduct(8, "Coffee Table", "Table", "table")

    user_selected = [table1, table2, table3]
    sorted_items = sorted(user_selected, key=get_category_reference_priority)
    assert [p.id for p in sorted_items] == [6, 7, 8]

    user_selected_rev = [table3, table1, table2]
    sorted_items_rev = sorted(user_selected_rev, key=get_category_reference_priority)
    assert [p.id for p in sorted_items_rev] == [8, 6, 7]


from unittest.mock import MagicMock, patch


def test_resolve_reference_images_prioritizes_anchor_furniture():
    """Verify _resolve_reference_images selects anchor furniture up to max_references."""
    img1 = Path("sofa.jpg")
    img6 = Path("table1.jpg")
    img7 = Path("table2.jpg")
    img9 = Path("lamp.jpg")

    sofa = DummyProduct(1, "Japandi Sofa", "Sofa", "sofa", image_url="sofa.jpg")
    table1 = DummyProduct(6, "Glass Table", "Table", "table", image_url="table1.jpg")
    table2 = DummyProduct(7, "Rattan Table", "Table", "table", image_url="table2.jpg")
    lamp = DummyProduct(9, "Floor Lamp", "Lighting", "lighting", image_url="lamp.jpg")

    mock_provider = MagicMock()
    mock_provider.MAX_INPUT_IMAGES = 4

    service = DesignGenerationService(db=MagicMock(), image_provider=mock_provider)
    storage_mock = MagicMock()
    storage_mock.resolve = lambda url: Path(url)

    service._primary_product_image = lambda p: p.images[0] if p.images else None

    import app.services.design_generation_service as dgs_module
    old_storage_cls = dgs_module.ProductImageStorageService
    dgs_module.ProductImageStorageService = lambda: storage_mock

    try:
        with patch.object(Path, "is_file", return_value=True):
            # User input order: Table1 (6), Lamp (9), Sofa (1), Table2 (7)
            selected_4 = [table1, lamp, sofa, table2]
            paths, mapping, inc_ids, miss_ids = service._resolve_reference_images(selected_4)

            # Expect top 3: Sofa (10), Table1 (30), Table2 (30) - Lamp (60) is dropped from visual slots
            assert inc_ids == [1, 6, 7]
            assert [p.id for _, p in mapping] == [1, 6, 7]
            assert [idx for idx, _ in mapping] == [1, 2, 3]
            assert miss_ids == []
            assert len(paths) == 3
            assert paths[0] == img1
            assert paths[1] == img6
            assert paths[2] == img7
    finally:
        dgs_module.ProductImageStorageService = old_storage_cls


def test_resolve_reference_images_case_1_2_3_products():
    """Verify 1, 2, and 3 products all fit into visual reference slots."""
    f1 = Path("p1.jpg")
    f2 = Path("p2.jpg")
    f3 = Path("p3.jpg")

    p1 = DummyProduct(1, "Sofa", "Sofa", "sofa", image_url="p1.jpg")
    p2 = DummyProduct(2, "Table", "Table", "table", image_url="p2.jpg")
    p3 = DummyProduct(3, "Lamp", "Lighting", "lighting", image_url="p3.jpg")

    mock_provider = MagicMock()
    mock_provider.MAX_INPUT_IMAGES = 4
    service = DesignGenerationService(db=MagicMock(), image_provider=mock_provider)
    service._primary_product_image = lambda p: p.images[0] if p.images else None

    import app.services.design_generation_service as dgs_module
    old_storage_cls = dgs_module.ProductImageStorageService
    storage_mock = MagicMock()
    storage_mock.resolve = lambda url: Path(url)
    dgs_module.ProductImageStorageService = lambda: storage_mock

    try:
        with patch.object(Path, "is_file", return_value=True):
            # 1 product
            paths, mapping, inc_ids, _ = service._resolve_reference_images([p1])
            assert inc_ids == [1]
            assert len(paths) == 1

            # 2 products
            paths, mapping, inc_ids, _ = service._resolve_reference_images([p2, p1])
            # Sofa priority 10 before Table priority 30
            assert inc_ids == [1, 2]
            assert len(paths) == 2

            # 3 products
            paths, mapping, inc_ids, _ = service._resolve_reference_images([p3, p2, p1])
            assert inc_ids == [1, 2, 3]
            assert len(paths) == 3
    finally:
        dgs_module.ProductImageStorageService = old_storage_cls


def test_resolve_reference_images_handles_missing_file():
    """Verify missing image file is excluded from reference slots and recorded in missing_ids."""
    p1 = DummyProduct(1, "Sofa", "Sofa", "sofa", image_url="/storage/products/nonexistent.jpg")
    p2 = DummyProduct(2, "Table", "Table", "table")  # No image at all

    mock_provider = MagicMock()
    mock_provider.MAX_INPUT_IMAGES = 4
    service = DesignGenerationService(db=MagicMock(), image_provider=mock_provider)
    service._primary_product_image = lambda p: p.images[0] if p.images else None

    import app.services.design_generation_service as dgs_module
    old_storage_cls = dgs_module.ProductImageStorageService
    storage_mock = MagicMock()
    storage_mock.resolve = lambda url: Path(url)  # Path does not exist on disk
    dgs_module.ProductImageStorageService = lambda: storage_mock

    try:
        paths, mapping, inc_ids, miss_ids = service._resolve_reference_images([p1, p2])
        assert inc_ids == []
        assert set(miss_ids) == {1, 2}
        assert paths == []
        assert mapping == []
    finally:
        dgs_module.ProductImageStorageService = old_storage_cls


def test_format_dimensions_filters_mock_placeholder():
    """Verify known dummy dimensions 80x70x60 are not asserted as physical truth."""
    dummy_prod = DummyProduct(1, "Sofa", "Sofa", "sofa", width=80.0, height=70.0, depth=60.0)
    assert _format_dimensions(dummy_prod) == "standard proportion"

    none_prod = DummyProduct(2, "Sofa", "Sofa", "sofa", width=None, height=None, depth=None)
    assert _format_dimensions(none_prod) == "standard proportion"

    custom_prod = DummyProduct(3, "Real Sofa", "Sofa", "sofa", width=210.0, height=85.0, depth=90.0)
    assert "210.0 x 85.0 x 90.0 cm (guide only)" in _format_dimensions(custom_prod)


def test_prompt_builder_distinguishes_referenced_and_text_only():
    """Verify referenced products and text-only products are clearly segregated in prompt."""
    p1 = DummyProduct(1, "Japandi Sofa", "Sofa", "sofa")
    p6 = DummyProduct(6, "Glass Table", "Table", "table")
    p7 = DummyProduct(7, "Rattan Table", "Table", "table")
    p9 = DummyProduct(9, "Floor Lamp", "Lighting", "lighting")

    project = make_dummy_project()
    analysis = make_dummy_analysis()
    preference = make_dummy_preference()

    all_products = [p1, p6, p7, p9]
    # Only 3 have visual reference images
    reference_mapping = [(1, p1), (2, p6), (3, p7)]

    prompt = build_design_generation_prompt(
        project=project,
        analysis=analysis,
        preference=preference,
        products=all_products,
        reference_mapping=reference_mapping,
    )

    # Check presence of key sections
    assert "REFERENCE 0: original room image." in prompt
    assert "REFERENCE 1: Product ID 1; name Japandi Sofa" in prompt
    assert "REFERENCE 2: Product ID 6; name Glass Table" in prompt
    assert "REFERENCE 3: Product ID 7; name Rattan Bedside" not in prompt  # name is Rattan Table
    assert "REFERENCE 3: Product ID 7; name Rattan Table" in prompt

    # Check referenced section
    assert "Primary products with visual reference images" in prompt
    assert "REFERENCE 1 -> Product ID 1: Japandi Sofa" in prompt
    assert "Fidelity: maintain silhouette, contour, color, and finish" in prompt

    # Check text-only section
    assert "Supplementary selected products (text-guided placement only, no reference image):" in prompt
    assert "Product ID 9: Floor Lamp; category Lighting" in prompt

    # Check length is well within Cloudflare 4096 limit
    assert len(prompt) < 4096
    assert PROMPT_VERSION == "v2"
