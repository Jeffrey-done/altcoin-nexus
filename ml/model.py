"""
ML 模型 - XGBoost 集成
"""

import logging
import numpy as np
from typing import Any, Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("nexus.ml")


@dataclass
class MLPrediction:
    """ML 预测结果"""
    probability: float  # 0-1
    confidence: float   # 0-1
    features_used: int
    model_version: str


class MLModel:
    """
    XGBoost 模型封装
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path
        self.model_version = "v1"
        self.feature_names: List[str] = []
        self._loaded = False
    
    def load(self) -> bool:
        """加载模型"""
        if self._loaded:
            return True
        
        try:
            import xgboost as xgb
            
            if self.model_path and Path(self.model_path).exists():
                self.model = xgb.XGBClassifier()
                self.model.load_model(self.model_path)
                self._loaded = True
                logger.info(f"ML model loaded from {self.model_path}")
                return True
            else:
                logger.warning("ML model file not found")
                return False
        
        except ImportError:
            logger.warning("xgboost not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            return False
    
    def predict(self, features: np.ndarray) -> Optional[MLPrediction]:
        """预测"""
        if not self._loaded and not self.load():
            return None
        
        try:
            # 概率预测
            proba = self.model.predict_proba(features.reshape(1, -1))[0]
            
            # 做空概率 (class 1)
            short_prob = proba[1] if len(proba) > 1 else proba[0]
            
            # 置信度 (基于概率距离 0.5 的程度)
            confidence = abs(short_prob - 0.5) * 2
            
            return MLPrediction(
                probability=float(short_prob),
                confidence=float(confidence),
                features_used=len(features),
                model_version=self.model_version,
            )
        
        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            return None
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """训练模型"""
        try:
            import xgboost as xgb
            from sklearn.model_selection import cross_val_score
            
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                use_label_encoder=False,
                eval_metric='logloss',
            )
            
            # 交叉验证
            scores = cross_val_score(self.model, X, y, cv=5, scoring='accuracy')
            
            # 训练完整模型
            self.model.fit(X, y)
            self._loaded = True
            
            if feature_names:
                self.feature_names = feature_names
            
            return {
                "accuracy_mean": float(scores.mean()),
                "accuracy_std": float(scores.std()),
                "samples": len(X),
                "features": X.shape[1],
            }
        
        except Exception as e:
            logger.error(f"ML training failed: {e}")
            return {"error": str(e)}


class MLScorer:
    """
    ML 评分器
    """
    
    def __init__(self, model: Optional[MLModel] = None):
        self.model = model or MLModel()
    
    def score(
        self,
        ohlcv: List[List],
        external_data: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        ML 评分
        
        Returns:
            {score, probability, confidence} or None
        """
        if not self.model._loaded and not self.model.load():
            return None
        
        try:
            # 提取特征
            features = self._extract_features(ohlcv, external_data)
            
            # 预测
            prediction = self.model.predict(features)
            
            if not prediction:
                return None
            
            # 转换为评分 (0-100)
            score = int(prediction.probability * 100)
            
            return {
                "score": score,
                "probability": prediction.probability,
                "confidence": prediction.confidence,
                "source": "ml",
                "model_version": prediction.model_version,
            }
        
        except Exception as e:
            logger.error(f"ML scoring failed: {e}")
            return None
    
    def _extract_features(
        self,
        ohlcv: List[List],
        external_data: Optional[Dict],
    ) -> np.ndarray:
        """提取特征向量"""
        features = []
        
        if len(ohlcv) < 20:
            return np.zeros(12)
        
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        
        # 1. RSI
        features.append(self._rsi(closes, 14))
        
        # 2. 24h 涨幅
        features.append((closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) > 1 else 0)
        
        # 3. 7d 涨幅
        features.append((closes[-1] - closes[-7]) / closes[-7] * 100 if len(closes) > 7 else 0)
        
        # 4. 波动率
        returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
        features.append(np.std(returns[-24:]) * 100 if len(returns) >= 24 else 0)
        
        # 5. 成交量比率
        avg_vol = np.mean(volumes[-7:]) if len(volumes) >= 7 else 1
        features.append(volumes[-1] / avg_vol if avg_vol > 0 else 1)
        
        # 6. 价格位置
        high_20 = max(closes[-20:])
        low_20 = min(closes[-20:])
        features.append((closes[-1] - low_20) / (high_20 - low_20) if high_20 != low_20 else 0.5)
        
        # 7. MA 交叉
        ma5 = np.mean(closes[-5:])
        ma20 = np.mean(closes[-20:])
        features.append((ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0)
        
        # 8. ATR
        tr_values = []
        for i in range(1, min(15, len(ohlcv))):
            high = ohlcv[-i][2]
            low = ohlcv[-i][3]
            prev_close = ohlcv[-i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
        features.append(np.mean(tr_values) if tr_values else 0)
        
        # 9. 量价背离
        if len(closes) >= 5:
            price_change = (closes[-1] - closes[-5]) / closes[-5]
            vol_change = (volumes[-1] - volumes[-5]) / volumes[-5] if volumes[-5] > 0 else 0
            features.append(price_change - vol_change)
        else:
            features.append(0)
        
        # 10. 资金费率
        if external_data and "funding_rate" in external_data:
            features.append(external_data["funding_rate"])
        else:
            features.append(0)
        
        # 11. 持仓量变化
        if external_data and "oi_change" in external_data:
            features.append(external_data["oi_change"])
        else:
            features.append(0)
        
        # 12. 趋势强度
        up_moves = [closes[i] - closes[i-1] for i in range(1, len(closes)) if closes[i] > closes[i-1]]
        down_moves = [closes[i-1] - closes[i] for i in range(1, len(closes)) if closes[i] < closes[i-1]]
        avg_up = np.mean(up_moves) if up_moves else 0
        avg_down = np.mean(down_moves) if down_moves else 0
        features.append(abs(avg_up - avg_down) / (avg_up + avg_down) * 100 if (avg_up + avg_down) > 0 else 0)
        
        return np.array(features)
    
    def _rsi(self, closes: List[float], period: int = 14) -> float:
        """计算 RSI"""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
