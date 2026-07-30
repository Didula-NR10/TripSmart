import numpy as np
from tensorflow.keras.models import load_model
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

artifacts_folder = r'C:\Users\pc\Desktop\TravelApp2\Forecast\artifacts'

model = load_model(r'C:\Users\pc\Desktop\TravelApp2\AppDev\extra\models\best_checkpoint.keras')

X_test = np.load(f"{artifacts_folder}\\X_test.npy")
y_test = np.load(f"{artifacts_folder}\\y_test.npy")

y_pred = model.predict(X_test, batch_size=32, verbose=1)

y_true_flat = y_test.reshape(-1, y_test.shape[-1])
y_pred_flat = y_pred.reshape(-1, y_pred.shape[-1])

r2 = r2_score(y_true_flat, y_pred_flat)
mse = mean_squared_error(y_true_flat, y_pred_flat)
rmse = np.sqrt(mse)
mae = mean_absolute_error(y_true_flat, y_pred_flat)

print(f"\n--- Evaluation Metrics ---")
print(f"R2 Score: {r2:.4f}")
print(f"MSE:      {mse:.4f}")
print(f"RMSE:     {rmse:.4f}")
print(f"MAE:      {mae:.4f}")