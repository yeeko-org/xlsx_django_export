"""
Modelos de prueba para tests del framework de exportación.

Simulan una estructura simplificada tipo OCSA:
Publisher → Article → Tag (M2M)
                   → Comment (reverse FK)
"""
from django.db import models


class Publisher(models.Model):
    name = models.CharField(
        max_length=100, verbose_name="nombre",
    )
    country = models.CharField(
        max_length=50, verbose_name="país", default="",
    )

    class Meta:
        app_label = "tests"
        verbose_name = "editorial"
        verbose_name_plural = "editoriales"

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    name = models.CharField(
        max_length=50, verbose_name="etiqueta",
    )

    class Meta:
        app_label = "tests"
        verbose_name = "etiqueta"

    def __str__(self) -> str:
        return self.name


class Article(models.Model):
    title = models.CharField(
        max_length=200, verbose_name="título",
    )
    body = models.TextField(
        verbose_name="cuerpo", default="",
    )
    published_date = models.DateField(
        verbose_name="fecha de publicación",
        null=True, blank=True,
    )
    word_count = models.IntegerField(
        verbose_name="conteo de palabras", default=0,
    )
    is_featured = models.BooleanField(
        verbose_name="destacado", default=False,
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.CASCADE,
        related_name="articles",
        verbose_name="editorial",
        null=True, blank=True,
    )
    tags = models.ManyToManyField(
        Tag,
        related_name="articles",
        verbose_name="etiquetas",
        blank=True,
    )

    class Meta:
        app_label = "tests"
        verbose_name = "artículo"

    def __str__(self) -> str:
        return self.title


class Comment(models.Model):
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="artículo",
    )
    author_name = models.CharField(
        max_length=100, verbose_name="nombre del autor",
    )
    text = models.TextField(
        verbose_name="texto",
    )
    created_at = models.DateTimeField(
        verbose_name="fecha de creación",
        auto_now_add=True,
    )

    class Meta:
        app_label = "tests"
        verbose_name = "comentario"

    def __str__(self) -> str:
        return f"{self.author_name}: {self.text[:30]}"
