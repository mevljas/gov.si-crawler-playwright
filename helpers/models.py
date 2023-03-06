from sqlalchemy import Table, Column, Integer, String, ForeignKey, Text, text, DateTime, \
    LargeBinary, MetaData
from sqlalchemy.orm import relationship, declarative_base

meta = MetaData(schema="public")
Base = declarative_base(metadata=meta)



class DataType(Base):
    __tablename__ = 'data_type'

    code = Column(String(20), primary_key=True, autoincrement=False)


class PageType(Base):
    __tablename__ = 'page_type'

    code = Column(String(20), primary_key=True, autoincrement=False)


class Site(Base):
    __tablename__ = 'site'

    id = Column(Integer, primary_key=True)
    domain = Column(String(500))
    robots_content = Column(Text)
    sitemap_content = Column(Text)


class Page(Base):
    __tablename__ = 'page'

    id = Column(Integer, primary_key=True)
    site_id = Column(ForeignKey('site.id', ondelete='RESTRICT'), index=True)
    page_type_code = Column(ForeignKey('page_type.code', ondelete='RESTRICT'), index=True)
    url = Column(String(3000), unique=True)
    html_content = Column(Text)
    http_status_code = Column(Integer)
    accessed_time = Column(DateTime)

    page_type = relationship('PageType')
    site = relationship('Site')
    relationship(back_populates="parent")


class Image(Base):
    __tablename__ = 'image'

    id = Column(Integer, primary_key=True)
    page_id = Column(ForeignKey('page.id', ondelete='RESTRICT'), index=True)
    filename = Column(String(255))
    content_type = Column(String(50))
    data = Column(LargeBinary)
    accessed_time = Column(DateTime)

    page = relationship('Page')


class Link(Base):
    __tablename__ = 'link'

    from_page = Column(ForeignKey('page.id', ondelete='RESTRICT'), primary_key=True, nullable=False,
                       index=True)
    to_page = Column(ForeignKey('page.id', ondelete='RESTRICT'), primary_key=True, nullable=False, index=True)
    relationship(back_populates="children")


class PageDatum(Base):
    __tablename__ = 'page_data'

    id = Column(Integer, primary_key=True)
    page_id = Column(ForeignKey('page.id', ondelete='RESTRICT'), index=True)
    data_type_code = Column(ForeignKey('data_type.code', ondelete='RESTRICT'), index=True)
    data = Column(LargeBinary)

    data_type = relationship('DataType')
    page = relationship('Page')
