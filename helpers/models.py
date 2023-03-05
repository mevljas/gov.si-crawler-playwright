from sqlalchemy import Table, Column, Integer, String, ForeignKey, Text, text, DateTime, \
    LargeBinary
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()
meta = Base.metadata


class DataType(Base):
    __tablename__ = 'data_type'
    __table_args__ = {'schema': 'public'}

    code = Column(String(20), primary_key=True, autoincrement=False)


class PageType(Base):
    __tablename__ = 'page_type'
    __table_args__ = {'schema': 'public'}

    code = Column(String(20), primary_key=True, autoincrement=False)


class Site(Base):
    __tablename__ = 'site'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True)
    domain = Column(String(500))
    robots_content = Column(Text)
    sitemap_content = Column(Text)


class Page(Base):
    __tablename__ = 'page'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True)
    site_id = Column(ForeignKey('public.site.id', ondelete='RESTRICT'), index=True)
    page_type_code = Column(ForeignKey('public.page_type.code', ondelete='RESTRICT'), index=True)
    url = Column(String(3000), unique=True)
    html_content = Column(Text)
    http_status_code = Column(Integer)
    accessed_time = Column(DateTime)

    page_type = relationship('PageType')
    site = relationship('Site')
    parents = relationship(
        'Page',
        secondary='public.link',
        primaryjoin='Page.id == link.c.from_page',
        secondaryjoin='Page.id == link.c.to_page'
    )


class Image(Base):
    __tablename__ = 'image'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True)
    page_id = Column(ForeignKey('public.page.id', ondelete='RESTRICT'), index=True)
    filename = Column(String(255))
    content_type = Column(String(50))
    data = Column(LargeBinary)
    accessed_time = Column(DateTime)

    page = relationship('Page')


t_link = Table(
    'link', meta,
    Column('from_page', ForeignKey('public.page.id', ondelete='RESTRICT'), primary_key=True, nullable=False, index=True),
    Column('to_page', ForeignKey('public.page.id', ondelete='RESTRICT'), primary_key=True, nullable=False, index=True),
    schema='public'
)


class PageDatum(Base):
    __tablename__ = 'page_data'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True)
    page_id = Column(ForeignKey('public.page.id', ondelete='RESTRICT'), index=True)
    data_type_code = Column(ForeignKey('public.data_type.code', ondelete='RESTRICT'), index=True)
    data = Column(LargeBinary)

    data_type = relationship('DataType')
    page = relationship('Page')
