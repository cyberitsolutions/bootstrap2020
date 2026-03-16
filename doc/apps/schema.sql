-- Estimate how much bigger --template=desktop-inmate would be if this package were added.
-- (Basically the sum of it and all its added dependencies.)
CREATE TABLE IF NOT EXISTS install_footprint (
    dsc_name TEXT NOT NULL,     -- only so udd staleness data can be joined easily
    deb_name TEXT PRIMARY KEY,
    -- required_space is the extracted size
    -- required_download is the .debs -- it will roughly match what filesystem.squashfs needs
    required_space INTEGER CHECK (required_space >= 0),  -- NULL if not installable (conflicts)
    required_download INTEGER CHECK (required_download >= 0),  -- NULL if not installable (conflicts)
    deb_summary TEXT NOT NULL);  -- the short en Description


CREATE TABLE IF NOT EXISTS reviews (
    deb_name TEXT NOT NULL REFERENCES install_footprint(deb_name),
    review_release INTEGER NOT NULL CHECK (review_release BETWEEN 9 AND 99),  -- e.g. 12 if reviewed on Debian 12
    is_passed INTEGER CHECK (is_passed IN (0, 1)),  -- PASS=1, FAIL=0, TODO=NULL
    notes TEXT,
    PRIMARY KEY (deb_name, review_release);


-- Every /usr/share/application/⋯.desktop.
CREATE TABLE IF NOT EXISTS dotdesktop (
    deb_name TEXT NOT NULL REFERENCES install_footprint(deb_name),  -- "apt install foo"
    file_name TEXT NOT NULL,    -- foo.desktop
    application_name TEXT,      -- Name[en_AU]=foo
    generic_name TEXT,          -- GenericName[en_AU]=foo
    categories JSONB,  -- e.g. Categories=Game;AdventureGame; -- usually dubious af
    PRIMARY KEY (binary_package, file_name));


-- e.g. junior-games-puzzle Depends: 2048-qt
CREATE TABLE IF NOT EXISTS metapackages (
    metapackage_name TEXT NOT NULL,
    strength INTEGER NOT NULL CHECK (strength IN (0,1,2)),  -- Suggests=0, Recommends=1, Depends=2
    deb_name TEXT NOT NULL REFERENCES install_footprint (deb_name),
    PRIMARY KEY (metapackage_name, strength, deb_name));


-- The last time a package was updated in Debian.
-- Proxy for "is this app dead/abandoned?"
CREATE TABLE IF NOT EXISTS staleness (
    dsc_name TEXT PRIMARY KEY REFERENCES install_footprint (dsc_name),
    year_of_last_update INTEGER NOT NULL CHECK (year_of_last_update BETWEEN 1990 AND 2100));

-- Relative popularity in Debian (not PrisonPC prisons).
-- Proxy for "is this app good?"
CREATE TABLE IF NOT EXISTS debian_votes (
    deb_name PRIMARY KEY REFERENCES install_footprint (deb_name),
    -- e.g. 0.05 = 5% of popcon users actively use this package
    percentage REAL NOT NULL CHECK (percentage BETWEEN 0 AND 1));

-- FIXME: CREATE TABLE IF NOT EXISTS shitlist (reason TEXT PRIMARY KEY, deb_names JSONB, dsc_names JSONB);
--        being something like ('Detainees are not allowed general-purpose programming tools.', '["games-perl-dev", "science-distributedcomputing"]', NULL);
