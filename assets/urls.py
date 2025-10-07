from django.urls import path
from . import views

urlpatterns = [
    # Employee CRUD
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/new/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='employee_update'),

    # AssetType CRUD
    path('asset-types/', views.AssetTypeListView.as_view(), name='assettype_list'),
    path('asset-types/new/', views.AssetTypeCreateView.as_view(), name='assettype_create'),
    path('asset-types/<int:pk>/edit/', views.AssetTypeUpdateView.as_view(), name='assettype_update'),
    path('asset-types/<int:pk>/soft-delete/', views.AssetTypeSoftDeleteView.as_view(), name='assettype_soft_delete'),

    # Asset CRUD
    path('assets/', views.AssetListView.as_view(), name='asset_list'),
    path('assets/<int:pk>/soft-delete/', views.AssetSoftDeleteView.as_view(), name='asset_soft_delete'),

    # Asset Assignment
    path('assets/assign/', views.AssetAssignmentView.as_view(), name='asset_assign'),

    # Employee Overview
    path('employees/overview/', views.EmployeeAssetOverviewView.as_view(), name='employee_overview'),

    # Employee Detail
    path('employees/<str:employee_id>/', views.EmployeeAssetDetailView.as_view(), name='employee_detail'),
    path('employees/<str:employee_id>/soft-delete/', views.EmployeeSoftDeleteView.as_view(), name='employee_soft_delete'),
    path('employees/<str:employee_id>/delete/', views.EmployeeDeleteView.as_view(), name='employee_delete'),

    # Assignment actions
    path('assign-asset/', views.AssignAssetToEmployeeView.as_view(), name='assign_asset_to_employee'),
    path('unassign-asset/<int:asset_id>/', views.UnassignAssetView.as_view(), name='unassign_asset'),
    path('api/unassigned-assets/<int:asset_type_id>/', views.UnassignedAssetsAPIView.as_view(), name='unassigned_assets_api'),
]
