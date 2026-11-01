from django.contrib import admin
from .models import (
    WorkCategory,
    ConstructionSite,
    SiteCategoryProgress,
    SiteTask,
    ProjectUpdateImage,
    SiteProgressHistory,
)


class SiteTaskInline(admin.TabularInline):
    model = SiteTask
    extra = 0
    fields = ('task_name', 'is_completed', 'completed_date', 'order')


class SiteCategoryProgressInline(admin.TabularInline):
    model = SiteCategoryProgress
    extra = 0
    fields = ('category', 'is_enabled', 'progress_percentage', 'updated_at')
    readonly_fields = ('updated_at',)


class ProjectUpdateImageInline(admin.TabularInline):
    model = ProjectUpdateImage
    extra = 0
    fields = ('image', 'caption', 'category', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


@admin.register(WorkCategory)
class WorkCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_mandatory', 'order')
    list_filter = ('is_mandatory',)
    search_fields = ('name', 'slug')


@admin.register(ConstructionSite)
class ConstructionSiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'client', 'status', 'display_overall_progress', 'start_date', 'estimated_completion_date')
    list_filter = ('status', 'start_date', 'estimated_completion_date')
    search_fields = ('name', 'client__username', 'client__email', 'site_address')
    inlines = [SiteCategoryProgressInline, ProjectUpdateImageInline]

    def display_overall_progress(self, obj):
        return f"{obj.calculate_overall_progress()}%"
    display_overall_progress.short_description = "Overall Progress"


@admin.register(SiteCategoryProgress)
class SiteCategoryProgressAdmin(admin.ModelAdmin):
    list_display = ('site', 'category', 'is_enabled', 'progress_percentage', 'updated_at')
    list_filter = ('is_enabled', 'category')
    search_fields = ('site__name', 'category__name')
    inlines = [SiteTaskInline]


@admin.register(SiteTask)
class SiteTaskAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'site_category', 'is_completed', 'completed_date', 'order')
    list_filter = ('is_completed', 'site_category__category')
    search_fields = ('task_name', 'site_category__site__name')


@admin.register(ProjectUpdateImage)
class ProjectUpdateImageAdmin(admin.ModelAdmin):
    list_display = ('site', 'caption', 'category', 'uploaded_at')
    list_filter = ('uploaded_at', 'category')
    search_fields = ('caption', 'site__name')


@admin.register(SiteProgressHistory)
class SiteProgressHistoryAdmin(admin.ModelAdmin):
    list_display = ('site', 'overall_progress', 'recorded_at', 'notes')
    list_filter = ('recorded_at',)
    search_fields = ('site__name', 'notes')

