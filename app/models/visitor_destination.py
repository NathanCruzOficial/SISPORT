from app import db


class VisitorDestinationGroup(db.Model):
    __tablename__ = "visitor_destination_groups"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)
    color = db.Column(db.String(20), nullable=False, default="#ffc107")

    parent_id = db.Column(
        db.Integer,
        db.ForeignKey("visitor_destination_groups.id", ondelete="CASCADE"),
        nullable=True,
    )

    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_root = db.Column(db.Boolean, nullable=False, default=False)

    parent = db.relationship(
        "VisitorDestinationGroup",
        remote_side=[id],
        back_populates="children",
    )

    children = db.relationship(
        "VisitorDestinationGroup",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="VisitorDestinationGroup.sort_order.asc(), VisitorDestinationGroup.name.asc()",
    )

    places = db.relationship(
        "VisitorDestinationPlace",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="VisitorDestinationPlace.sort_order.asc(), VisitorDestinationPlace.name.asc()",
    )

    def __repr__(self):
        return f"<VisitorDestinationGroup {self.id} - {self.name}>"

    @property
    def path_names(self):
        names = []
        current = self

        while current:
            names.append(current.name)
            current = current.parent

        return list(reversed(names))

    @property
    def path(self):
        return " > ".join(self.path_names)

    def total_places_count(self):
        total = len(self.places)

        for child in self.children:
            total += child.total_places_count()

        return total

    def total_groups_count(self):
        total = len(self.children)

        for child in self.children:
            total += child.total_groups_count()

        return total

    def is_ancestor_of(self, other_group):
        current = other_group.parent

        while current:
            if current.id == self.id:
                return True

            current = current.parent

        return False


class VisitorDestinationPlace(db.Model):
    __tablename__ = "visitor_destination_places"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    group_id = db.Column(
        db.Integer,
        db.ForeignKey("visitor_destination_groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    group = db.relationship(
        "VisitorDestinationGroup",
        back_populates="places",
    )

    def __repr__(self):
        return f"<VisitorDestinationPlace {self.id} - {self.name}>"

    @property
    def color(self):
        if self.group:
            return self.group.color

        return "#6c757d"

    @property
    def path(self):
        if self.group:
            return f"{self.group.path} > {self.name}"

        return self.name
